"""Run existing seed scripts to prepare reproducible E2E data.

This script calls the project seed scripts in a safe, idempotent way.
"""
import os
import subprocess
import sys


def main():
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    # Seed gamification
    gamif = os.path.join(repo, 'scripts', 'seed_gamification.py')
    if os.path.exists(gamif):
        print('Running seed_gamification.py')
        subprocess.run([sys.executable, gamif], check=False)

    # Load GTFS if present
    gtfs = os.path.join(repo, 'backend', 'load_gtfs.py')
    if os.path.exists(gtfs):
        print('Running backend/load_gtfs.py')
        subprocess.run([sys.executable, gtfs], check=False)

    print('E2E seed completed')


if __name__ == '__main__':
    main()
