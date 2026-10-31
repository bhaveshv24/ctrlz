"""Create a private Render environment template with unique generated account passwords."""
import argparse
import os
import secrets
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('deploy/.env.render.local'))
    parser.add_argument('--admin1', default='admin1@ctrlz.local')
    parser.add_argument('--admin2', default='admin2@ctrlz.local')
    parser.add_argument('--user', default='user@ctrlz.local')
    args = parser.parse_args()
    emails = [args.admin1.strip().lower(), args.admin2.strip().lower(), args.user.strip().lower()]
    if len(set(emails)) != 3 or any('\n' in e or '\r' in e or '@' not in e or '.' not in e.rsplit('@',1)[-1] for e in emails):
        parser.error('Supply three distinct valid email addresses')
    values = {
        'CTRLZ_ADMIN_1_EMAIL': emails[0], 'CTRLZ_ADMIN_1_PASSWORD': secrets.token_urlsafe(30),
        'CTRLZ_ADMIN_2_EMAIL': emails[1], 'CTRLZ_ADMIN_2_PASSWORD': secrets.token_urlsafe(30),
        'CTRLZ_USER_EMAIL': emails[2], 'CTRLZ_USER_PASSWORD': secrets.token_urlsafe(30),
        'NVIDIA_API_KEY': '', 'NVIDIA_MODEL': 'nvidia/nemotron-3.5-lightning-30b-a3b',
        'CTRLZ_CORS_ORIGINS': 'https://YOUR-FRONTEND.vercel.app',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        parser.error('Output already exists. Existing credentials were preserved')
    with os.fdopen(fd, 'w') as handle:
        handle.write('# Private hosted bootstrap values. Never commit or share this file.\n')
        handle.write('\n'.join(f'{key}={value}' for key, value in values.items()) + '\n')
    print(f'Created private template: {args.output.resolve()}')
    print('Fill NVIDIA_API_KEY and the final frontend origin locally; copy values into Render secret fields.')
    print('Existing hosted account passwords are not changed by editing bootstrap values.')


if __name__ == '__main__':
    main()
