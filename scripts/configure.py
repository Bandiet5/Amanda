"""Create a private environment file with a fresh secret; never prints secrets."""
import argparse
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser(description='Configure Amanda se Kersfees without default secrets')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--development', action='store_true')
    mode.add_argument('--production', action='store_true')
    parser.add_argument('--origin', help='Exact origin, e.g. https://gifts.your-company.co.za')
    parser.add_argument('--database', default=str(Path(__file__).resolve().parent.parent / 'instance' / 'amanda.sqlite3'))
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent.parent / '.env')
    args = parser.parse_args()
    origin = (args.origin or ('http://localhost:5173' if args.development else '')).rstrip('/')
    parsed = urlsplit(origin)
    if not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        parser.error('Supply an exact --origin with a hostname and no path or credentials.')
    if args.production and parsed.scheme != 'https':
        parser.error('Production requires an https:// origin.')
    if args.development and parsed.scheme not in ('http', 'https'):
        parser.error('Development origin must use http:// or https://.')
    database = str(Path(args.database).expanduser().resolve())
    if '\n' in database or '"' in database or '\n' in origin or '"' in origin:
        parser.error('Invalid configuration value.')
    text = (f'APP_ENV={"development" if args.development else "production"}\n'
            f'SECRET_KEY={secrets.token_urlsafe(48)}\n'
            f'PUBLIC_ORIGIN={origin}\n'
            f'DATABASE_PATH="{Path(database).as_posix()}"\n'
            f'ALLOW_INSECURE_HTTP={"1" if args.development and parsed.scheme == "http" else "0"}\n')
    try:
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        parser.error('The environment file already exists. Edit it deliberately; it will not be overwritten.')
    with os.fdopen(fd, 'w', encoding='utf-8') as file:
        file.write(text)
    print(f'Created {args.output} with a fresh secret. Next: python -m server.cli set-admin-password')


if __name__ == '__main__':
    main()
