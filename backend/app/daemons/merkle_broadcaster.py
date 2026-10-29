"""Compatibility import; use hash_broadcaster for the sequential hash-chain daemon."""

from backend.app.daemons.hash_broadcaster import SequentialHashChainBroadcaster, main

__all__ = ["SequentialHashChainBroadcaster", "main"]


if __name__ == "__main__":
    main()
