import os
import shutil
import json
import random
import mimetypes
import time
import signal
import psutil
from PIL import Image
from typing import List
from cog import BasePredictor, Input, Path
from helpers.comfyui import ComfyUI
from threading import Thread, Lock

OUTPUT_DIR = "/tmp/outputs"
INPUT_DIR = "/tmp/inputs"
COMFYUI_TEMP_OUTPUT_DIR = "ComfyUI/temp"
TIMEOUT_SECONDS = 20  # 20s 超时

mimetypes.add_type("image/webp", ".webp")

with open("sticker_maker_api.json", "r") as file:
    workflow_json = file.read()

def find_and_kill_cog_server():
    """找到并终止 cog server 进程"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and 'python' in cmdline[0] and '-m' in cmdline and 'cog.server.http' in cmdline:
                os.kill(proc.info['pid'], signal.SIGTERM)
                print(f"Terminated cog server process (PID: {proc.info['pid']})")
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

class Predictor(BasePredictor):
    def setup(self):
        self.comfyUI = ComfyUI("127.0.0.1:8188")
        self.comfyUI.start_server(OUTPUT_DIR, INPUT_DIR)
        self.comfyUI.load_workflow(workflow_json)
        self.last_request_time = None  # 初始化为 None，表示还没有收到过请求
        self.is_predicting = False  # 标记是否正在执行预测
        self.lock = Lock()  # 用于线程安全的状态更新
        
        # 启动监控线程
        self.monitor_thread = Thread(target=self._monitor_requests, daemon=True)
        self.monitor_thread.start()

    def _monitor_requests(self):
        """监控请求时间的线程函数"""
        while True:
            # 只有在有过请求且当前没有进行预测的情况下才检查
            if self.last_request_time is not None and not self.is_predicting:
                current_time = time.time()
                if current_time - self.last_request_time > TIMEOUT_SECONDS:
                    print("No requests for 5 seconds, killing cog server...")
                    if find_and_kill_cog_server():
                        with self.lock:
                            self.last_request_time = None  # 重置为初始状态，等待新的请求
            time.sleep(5)  # 每5秒检查一次

    def cleanup(self):
        self.comfyUI.clear_queue()
        for directory in [OUTPUT_DIR, INPUT_DIR, COMFYUI_TEMP_OUTPUT_DIR]:
            if os.path.exists(directory):
                shutil.rmtree(directory)
            os.makedirs(directory)

    def update_workflow(self, workflow, **kwargs):
        workflow["6"]["inputs"]["text"] = (
            f"Sticker, {kwargs.get('prompt')}, svg, solid color background"
        )
        workflow["7"]["inputs"]["text"] = (
            f"nsfw, nude, {kwargs.get('negative_prompt')}, photo, photography"
        )

        empty_latent_image = workflow["5"]["inputs"]
        empty_latent_image["width"] = kwargs.get("width")
        empty_latent_image["height"] = kwargs.get("height")
        empty_latent_image["batch_size"] = kwargs.get("number_of_images")

        scheduler = workflow["3"]["inputs"]
        scheduler["seed"] = kwargs.get("seed")
        scheduler["steps"] = kwargs.get("steps")

    def log_and_collect_files(self, directory, prefix=""):
        files = []
        for f in os.listdir(directory):
            if f == "__MACOSX":
                continue
            path = os.path.join(directory, f)
            if os.path.isfile(path):
                print(f"{prefix}{f}")
                files.append(Path(path))
            elif os.path.isdir(path):
                print(f"{prefix}{f}/")
                files.extend(self.log_and_collect_files(path, prefix=f"{prefix}{f}/"))
        return files

    def predict(
        self,
        prompt: str = Input(default="a cute cat"),
        negative_prompt: str = Input(
            default="",
            description="Things you do not want in the image",
        ),
        width: int = Input(default=1152),
        height: int = Input(default=1152),
        steps: int = Input(default=17),
        number_of_images: int = Input(
            default=1, ge=1, le=10, description="Number of images to generate"
        ),
        output_format: str = Input(
            description="Format of the output images",
            choices=["webp", "jpg", "png"],
            default="webp",
        ),
        output_quality: int = Input(
            description="Quality of the output images, from 0 to 100. 100 is best quality, 0 is lowest quality.",
            default=90,
            ge=0,
            le=100,
        ),
        seed: int = Input(
            default=-1, description="Fix the random seed for reproducibility. Use -1 for random seed"
        ),
    ) -> List[Path]:
        """Run a single prediction on the model"""
        try:
            with self.lock:
                self.is_predicting = True  # 标记开始预测
                self.last_request_time = time.time()
            
            self.cleanup()

            if seed == -1:
                seed = random.randint(0, 2**32 - 1)
                print(f"Random seed set to: {seed}")

            workflow = json.loads(workflow_json)

            self.update_workflow(
                workflow,
                width=width,
                height=height,
                steps=steps,
                prompt=prompt,
                negative_prompt=negative_prompt,
                number_of_images=number_of_images,
                seed=seed,
            )

            wf = self.comfyUI.load_workflow(workflow)
            self.comfyUI.connect()
            self.comfyUI.run_workflow(wf)
            files = self.log_and_collect_files(OUTPUT_DIR)

            if output_quality < 100 or output_format in ["webp", "jpg"]:
                optimised_files = []
                for file in files:
                    if file.is_file() and file.suffix in [".jpg", ".jpeg", ".png"]:
                        image = Image.open(file)
                        optimised_file_path = file.with_suffix(f".{output_format}")
                        image.save(
                            optimised_file_path,
                            quality=output_quality,
                            optimize=True,
                        )
                        optimised_files.append(optimised_file_path)
                    else:
                        optimised_files.append(file)

                files = optimised_files

            return files
        finally:
            with self.lock:
                self.is_predicting = False  # 标记预测结束