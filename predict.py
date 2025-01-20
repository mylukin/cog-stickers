import os
import shutil
import json
import random
import mimetypes
from PIL import Image
from typing import List
import time
import threading
import torch
from cog import BasePredictor, Input, Path
from helpers.comfyui import ComfyUI

OUTPUT_DIR = "/tmp/outputs"
INPUT_DIR = "/tmp/inputs"
COMFYUI_TEMP_OUTPUT_DIR = "ComfyUI/temp"
IDLE_TIMEOUT = 60  # 1分钟超时

mimetypes.add_type("image/webp", ".webp")

with open("sticker_maker_api.json", "r") as file:
    workflow_json = file.read()

class Predictor(BasePredictor):
    def setup(self):
        self.comfyUI = ComfyUI("127.0.0.1:8188")
        self.comfyUI.start_server(OUTPUT_DIR, INPUT_DIR)
        self.comfyUI.load_workflow(workflow_json)
        self.last_request_time = time.time()
        self.cleanup_timer = None
        self.start_cleanup_timer()

    def start_cleanup_timer(self):
        """启动清理定时器"""
        if self.cleanup_timer is not None:
            self.cleanup_timer.cancel()
        
        self.cleanup_timer = threading.Timer(IDLE_TIMEOUT, self.cleanup_gpu_memory)
        self.cleanup_timer.daemon = True  # 设置为守护线程
        self.cleanup_timer.start()

    def cleanup_gpu_memory(self):
        """清理 GPU 显存"""
        print("Cleaning up GPU memory due to inactivity...")
        try:
            # 停止 ComfyUI 服务
            self.comfyUI.stop_server()
            
            # 清理 ComfyUI 相关资源
            self.comfyUI.clear_queue()
            
            # 强制执行 Python 的垃圾回收
            import gc
            gc.collect()
            
            # 清理 PyTorch 缓存
            if torch.cuda.is_available():
                # 释放所有未使用的缓存
                torch.cuda.empty_cache()
                # 重置峰值内存统计
                torch.cuda.reset_peak_memory_stats()
                # 同步所有 CUDA 流
                torch.cuda.synchronize()
            
            print("GPU memory cleaned up")
            
            # 重新启动 ComfyUI 服务
            self.comfyUI.start_server(OUTPUT_DIR, INPUT_DIR)
            self.comfyUI.load_workflow(workflow_json)
            
        except Exception as e:
            print(f"Error during GPU cleanup: {str(e)}")
            # 确保服务器重新启动
            try:
                self.comfyUI.start_server(OUTPUT_DIR, INPUT_DIR)
                self.comfyUI.load_workflow(workflow_json)
            except Exception as e2:
                print(f"Error restarting server: {str(e2)}")

    def cleanup(self):
        """清理临时文件和目录"""
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
            default=None, description="Fix the random seed for reproducibility"
        ),
    ) -> List[Path]:
        """Run a single prediction on the model"""
        # 更新最后请求时间
        self.last_request_time = time.time()
        # 重置清理定时器
        self.start_cleanup_timer()

        self.cleanup()

        if seed is None:
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

    def __del__(self):
        """析构函数：确保清理定时器被正确关闭"""
        if self.cleanup_timer:
            self.cleanup_timer.cancel()