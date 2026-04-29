"""
支持的模型及其参数白名单。
前端渲染表单与后端参数校验均以此为准，确保用户不能绕过限制。
"""
from typing import Any

# 精简后的宽高比，兼顾横/竖/方图常用场景
COMMON_ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "2:3"]

MODELS: dict[str, dict[str, Any]] = {
    "nanoBanana2": {
        "display_name": "Nano Banana 2",
        "task_type": "image",
        "max_num_images": 1,
        "max_reference_images": 2,
        # rewritePrompt 强制 false（上游默认开启 AI 改写，这里关掉以保持用户 prompt 原样）
        "fixed_params": {"rewritePrompt": False},
        "params": {
            "resolution": {"type": "dropdown", "options": ["1K", "2K"], "default": "1K", "label": "分辨率"},
            "aspectRatio": {"type": "dropdown", "options": COMMON_ASPECT_RATIOS, "default": "1:1", "label": "宽高比"},
        },
    },
    "nanoBananaPro": {
        "display_name": "Nano Banana Pro",
        "task_type": "image",
        "max_num_images": 2,
        "max_reference_images": 2,
        "fixed_params": {"rewritePrompt": False},
        "params": {
            "resolution": {"type": "dropdown", "options": ["1K", "2K"], "default": "1K", "label": "分辨率"},
            "aspectRatio": {"type": "dropdown", "options": COMMON_ASPECT_RATIOS, "default": "1:1", "label": "宽高比"},
        },
    },
    "gptImage2": {
        "display_name": "GPT Image 2",
        "task_type": "image",
        "max_num_images": 1,
        "max_reference_images": 2,
        # quality 锁定为 auto，rewritePrompt 锁定为 false
        "fixed_params": {"quality": "low", "rewritePrompt": False},
        "params": {
            "size": {
                "type": "dropdown",
                "options": [
                    "1024x1024", "1536x1024", "1024x1536",
                    "2048x2048", "2048x1152", "1152x2048",
                    "2048x1536", "1536x2048",
                    # "3840x2160", "2160x3840", "3840x1280", "1280x3840",
                ],
                "default": "1024x1024",
                "label": "尺寸",
            },
        },
    },
    "grokImagineImage": {
        "display_name": "Grok Imagine Image",
        "task_type": "image",
        "max_num_images": 1,
        "max_reference_images": 2,  # 纯文生图
        "fixed_params": {"rewritePrompt": False},
        "params": {
            "aspectRatio": {
                "type": "dropdown",
                "options": [
                    "1:1", "2:1", "20:9", "16:9", "4:3", "3:2",
                    "2:3", "3:4", "9:16", "9:20", "1:2",
                ],
                "default": "1:1",
                "label": "宽高比",
            },
        },
    },
    "grokImagineVideo": {
        "display_name": "Grok Imagine Video",
        "task_type": "video",
        "max_num_images": 1,
        "max_reference_images": 0,  # 纯文生视频
        "fixed_params": {"rewritePrompt": False},
        "params": {
            "duration": {
                "type": "dropdown",
                "options": ["5", "6", "7"],
                "default": "5",
                "label": "时长（秒）",
            },
            "resolution": {"type": "dropdown", "options": ["480p"], "default": "480p", "label": "分辨率"},
            "aspectRatio": {
                "type": "dropdown",
                "options": ["1:1", "16:9", "9:16"],
                "default": "16:9",
                "label": "宽高比",
            },
        },
    },
}


def validate_and_normalize_params(model: str, raw_params: dict, num_images: int) -> dict:
    """按白名单校验 & 规范化参数，返回透传给上游的 params。抛 ValueError 表示非法。"""
    cfg = MODELS.get(model)
    if not cfg:
        raise ValueError(f"不支持的模型: {model}")

    if num_images < 1 or num_images > cfg["max_num_images"]:
        raise ValueError(f"生成数量必须在 1-{cfg['max_num_images']} 之间")

    out: dict[str, Any] = {}
    for key, spec in cfg["params"].items():
        raw = raw_params.get(key, spec["default"])
        if spec["type"] == "dropdown":
            if raw not in spec["options"]:
                raise ValueError(f"参数 {key}={raw} 不在允许值 {spec['options']} 内")
            out[key] = raw
        elif spec["type"] == "switch":
            out[key] = bool(raw)
    # 强制参数覆盖（如 gptImage2 quality=auto）
    for k, v in cfg.get("fixed_params", {}).items():
        out[k] = v
    return out


def get_public_model_list() -> list[dict]:
    """返回前端可见的模型定义（不含 fixed_params）。"""
    result = []
    for key, cfg in MODELS.items():
        result.append({
            "key": key,
            "display_name": cfg["display_name"],
            "task_type": cfg["task_type"],
            "max_num_images": cfg["max_num_images"],
            "max_reference_images": cfg["max_reference_images"],
            "params": cfg["params"],
        })
    return result
