import asyncio
import argparse

from src.stream import LiveStreamStats

def main():
    parser = argparse.ArgumentParser(
        description="Simple CLI tool for getting NCAA Basketball game stats."
    )
    parser.add_argument(
        "--sports-code",
        type=str,
        help="The sports code to use when looking up games by date.",
        choices=["WBB", "MBB"],
        required=True,
    )
    parser.add_argument(
        "--game-id",
        type=int,
        help="The ID of the boxscore to retrieve game stats from.",
        required=True,
    )
    args = parser.parse_args()

    stats = LiveStreamStats(args.sports_code, args.game_id)
    asyncio.run(stats.stream())

if __name__ == '__main__':
    main()
