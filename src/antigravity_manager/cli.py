"""JSON CLI using exactly the same service as the manager; no Qt import required."""
import argparse
import json
from .service import ManagerService, DataError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir')
    parser.add_argument('--app-dir')
    parser.add_argument('--revision', type=int)
    parser.add_argument('--confirm', action='store_true', help='Confirm install/restore or fixed-text network test')
    parser.add_argument('action', choices=('status', 'config', 'probe', 'apply', 'restore', 'launch', 'diagnostics'))
    args = parser.parse_args(argv)
    kwargs = {}
    if args.action in ('status', 'apply', 'restore', 'launch'):
        kwargs['app_dir'] = args.app_dir
    if args.action in ('apply', 'restore', 'probe'):
        kwargs['confirmed'] = args.confirm
    if args.action == 'probe':
        kwargs['revision'] = args.revision
    try:
        result = ManagerService(data_dir=args.data_dir).execute(args.action, **kwargs)
    except DataError as error:
        result = {'ok': False, 'code': 'invalid_data', 'message': str(error)}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
