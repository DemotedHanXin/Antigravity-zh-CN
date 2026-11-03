"""Manage dictionaries and seven-day translation candidates without a GUI or API."""
import argparse
import json
from pathlib import Path

from translation_config import DataError, UserStore
from translation_service import DictionaryService


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--data-dir', type=Path,
                        help='Explicit user-data directory (use an isolated directory for tests)')
    commands = result.add_subparsers(dest='action', required=True)
    listing = commands.add_parser('list', help='List builtin and personal entries and dictionaryRevision')
    listing.add_argument('--query', default='')
    commands.add_parser('pending', help='List active candidates, persistent rejections and candidatesRevision')
    commands.add_parser('cleanup', help='Remove expired candidates without making requests')
    for name in ('set', 'restore-default', 'accept', 'reject', 'unblock'):
        command = commands.add_parser(name)
        command.add_argument('--source', required=True)
        command.add_argument('--revision', required=True, type=int,
                             help='dictionaryRevision for set/restore-default; candidatesRevision for review')
        if name in ('set', 'accept'):
            command.add_argument('--translation', required=name == 'set',
                                 help='Replacement text; accept uses the candidate when omitted')
    return result


def main(argv=None):
    args = vars(parser().parse_args(argv))
    try:
        service = DictionaryService(UserStore(directory=args.pop('data_dir')))
        result = service.execute(**args)
    except DataError as error:
        result = {'ok': False, 'code': 'invalid_data', 'message': str(error)}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
