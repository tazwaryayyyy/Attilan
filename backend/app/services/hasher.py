import hashlib
from typing import BinaryIO, Tuple
import blake3


class CryptographicHasher:
    """Computes dual cryptographic digests (SHA-256 and BLAKE3) over input streams."""

    CHUNK_SIZE: int = 65536  # 64 KB chunks

    @classmethod
    def compute_stream_hashes(cls, stream: BinaryIO) -> Tuple[str, str, int]:
        """
        Reads a binary stream sequentially and calculates both SHA-256 and BLAKE3 digests.
        Returns:
            Tuple[sha256_hex, blake3_hex, total_bytes]
        """
        sha256 = hashlib.sha256()
        blake3_hasher = blake3.blake3()
        total_bytes = 0

        stream.seek(0)
        while chunk := stream.read(cls.CHUNK_SIZE):
            sha256.update(chunk)
            blake3_hasher.update(chunk)
            total_bytes += len(chunk)

        stream.seek(0)
        return sha256.hexdigest(), blake3_hasher.hexdigest(), total_bytes

    @classmethod
    def compute_bytes_hashes(cls, data: bytes) -> Tuple[str, str, int]:
        """
        Calculates SHA-256 and BLAKE3 digests over in-memory raw bytes.
        """
        sha256_hex = hashlib.sha256(data).hexdigest()
        blake3_hex = blake3.blake3(data).hexdigest()
        return sha256_hex, blake3_hex, len(data)
