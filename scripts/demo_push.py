"""推送演示: 把演示库当前未处理告警摘要推送到群机器人。

用途: 验证 watcher + webhook 配置是否正确 (相当于 watcher 的一轮真实检查)。
用法: python scripts/demo_push.py [--platform wechat] [--text 自定义文案]
前置: config.yaml -> notify.wechat_webhook / dingtalk_webhook 已配置
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.mock_mes import MockMESAdapter
from app.watcher.alarm_watcher import build_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", default="wechat", choices=["wechat", "dingtalk", "both"])
    parser.add_argument("--text", default="", help="自定义文案; 省略则推送演示库未处理告警摘要")
    args = parser.parse_args()

    from app.notify import webhook

    text = args.text
    if not text:
        alarms = MockMESAdapter().get_alarms(hours=24 * 7, only_open=True)
        critical = [a for a in alarms if a.get("level") in ("ALARM", "CRITICAL")]
        text = build_summary(critical) or "(演示库当前没有 ALARM/CRITICAL 级未处理告警)"
        text = f"[轮询检查演示] {text}"

    result = webhook.send(args.platform, text, user="demo")
    print("推送结果:", result)


if __name__ == "__main__":
    main()
