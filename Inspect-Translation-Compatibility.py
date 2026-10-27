# coding: utf-8
"""Read-only fingerprint evidence for an already extracted application copy."""
import argparse
import json
from pathlib import Path
from translation_integration import fingerprints, select_profile


def main(argv=None):
    parser = argparse.ArgumentParser(description='只读检查已解包的应用副本；不会启用 AI、修改安装或发送网络请求。')
    parser.add_argument('extracted_app', type=Path, help='包含 package.json 的已解包应用副本')
    parser.add_argument('--ui-file', action='append', default=[], help='要核对的 UI 资源相对路径，可重复')
    args = parser.parse_args(argv)
    try:
        report = fingerprints(args.extracted_app, args.ui_file)
        profile = select_profile(args.extracted_app)
        report['matchedProfile'] = profile['id'] if profile else None
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print('[错误] ' + str(error))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
