"""
Binary Protocol Layer (Layer 0)
===============================

High-performance binary protocol using MessagePack for agent-to-agent
communication. Optimized for speed over human readability.

Wire Format:
    ┌─────────┬─────────┬──────────┬──────────────────┐
    │ Version │  Type   │  Length  │     Payload      │
    │ 1 byte  │ 2 bytes │ 4 bytes  │    variable      │
    └─────────┴─────────┴──────────┴──────────────────┘
    Header: 7 bytes total

Performance Target: <1ms per message encode/decode

ThinkingMachines [He2025] Compliance:
- Fixed wire format (version byte prevents breaking changes)
- Deterministic serialization via msgpack
- Length-prefixed for safe streaming
"""

import struct
from typing import Iterator, List, Union
import logging

try:
    import msgpack
except ImportError:
    msgpack = None

from .message_types import Message, MessageType, ProtocolError

logger = logging.getLogger(__name__)


class BinaryProtocolError(ProtocolError):
    """Exception for binary protocol errors."""
    pass


class BinaryProtocol:
    """
    Binary protocol encoder/decoder for high-performance messaging.

    Uses MessagePack for payload serialization and a fixed header format
    for efficient parsing. Suitable for agent-to-agent communication
    where performance matters more than human readability.

    Wire Format:
        - Version (1 byte): Protocol version (currently 0x01)
        - Type (2 bytes): MessageType value, big-endian
        - Length (4 bytes): Payload length in bytes, big-endian
        - Payload (variable): MessagePack-encoded message data

    Example:
        >>> proto = BinaryProtocol()
        >>> msg = Message(type=MessageType.HEARTBEAT)
        >>> encoded = proto.encode(msg)
        >>> decoded = proto.decode(encoded)
        >>> assert decoded.type == msg.type
    """

    VERSION = 0x01
    HEADER_FORMAT = '>BHI'  # version(1), type(2), length(4) = 7 bytes
    HEADER_SIZE = 7
    MAX_PAYLOAD_SIZE = 10 * 1024 * 1024  # 10MB limit

    def __init__(self):
        """Initialize binary protocol."""
        if msgpack is None:
            raise BinaryProtocolError(
                "msgpack is required for binary protocol. "
                "Install with: pip install msgpack"
            )

    def encode(self, message: Message) -> bytes:
        """
        Encode a message to binary format.

        Args:
            message: Message to encode

        Returns:
            Binary-encoded message

        Raises:
            BinaryProtocolError: If encoding fails
        """
        try:
            # Serialize payload with MessagePack
            payload_data = message.to_dict()
            # Remove type from payload since it's in header
            payload_for_wire = {
                k: v for k, v in payload_data.items() if k != 'type'
            }
            payload = msgpack.packb(payload_for_wire, use_bin_type=True)

            if len(payload) > self.MAX_PAYLOAD_SIZE:
                raise BinaryProtocolError(
                    f"Payload too large: {len(payload)} > {self.MAX_PAYLOAD_SIZE}"
                )

            # Build header
            header = struct.pack(
                self.HEADER_FORMAT,
                self.VERSION,
                message.type.value,
                len(payload)
            )

            return header + payload

        except struct.error as e:
            raise BinaryProtocolError(f"Header packing failed: {e}") from e
        except Exception as e:
            raise BinaryProtocolError(f"Encoding failed: {e}") from e

    def decode(self, data: bytes) -> Message:
        """
        Decode a binary message.

        Args:
            data: Binary data to decode

        Returns:
            Decoded Message

        Raises:
            BinaryProtocolError: If decoding fails
        """
        if len(data) < self.HEADER_SIZE:
            raise BinaryProtocolError(
                f"Data too short: {len(data)} < {self.HEADER_SIZE}"
            )

        try:
            # Parse header
            version, msg_type, length = struct.unpack(
                self.HEADER_FORMAT,
                data[:self.HEADER_SIZE]
            )

            if version != self.VERSION:
                raise BinaryProtocolError(
                    f"Unsupported protocol version: {version} (expected {self.VERSION})"
                )

            if len(data) < self.HEADER_SIZE + length:
                raise BinaryProtocolError(
                    f"Incomplete message: expected {self.HEADER_SIZE + length}, "
                    f"got {len(data)}"
                )

            # Decode payload
            payload_bytes = data[self.HEADER_SIZE:self.HEADER_SIZE + length]
            payload_data = msgpack.unpackb(payload_bytes, raw=False)

            # Reconstruct message dict with type
            payload_data['type'] = msg_type

            return Message.from_dict(payload_data)

        except struct.error as e:
            raise BinaryProtocolError(f"Header unpacking failed: {e}") from e
        except msgpack.exceptions.UnpackException as e:
            raise BinaryProtocolError(f"MessagePack decode failed: {e}") from e
        except ProtocolError:
            raise
        except Exception as e:
            raise BinaryProtocolError(f"Decoding failed: {e}") from e

    def stream_encode(self, messages: Iterator[Message]) -> bytes:
        """
        Encode multiple messages for streaming.

        Args:
            messages: Iterator of messages to encode

        Returns:
            Concatenated binary data
        """
        return b''.join(self.encode(m) for m in messages)

    def stream_decode(self, data: bytes) -> List[Message]:
        """
        Decode multiple messages from a stream.

        Args:
            data: Binary data containing multiple messages

        Returns:
            List of decoded messages

        Raises:
            BinaryProtocolError: If any message fails to decode
        """
        messages = []
        offset = 0

        while offset < len(data):
            if len(data) - offset < self.HEADER_SIZE:
                raise BinaryProtocolError(
                    f"Truncated message at offset {offset}"
                )

            # Peek at length from header
            _, _, length = struct.unpack(
                self.HEADER_FORMAT,
                data[offset:offset + self.HEADER_SIZE]
            )

            message_end = offset + self.HEADER_SIZE + length
            if message_end > len(data):
                raise BinaryProtocolError(
                    f"Incomplete message at offset {offset}: "
                    f"need {message_end}, have {len(data)}"
                )

            # Decode single message
            msg_data = data[offset:message_end]
            messages.append(self.decode(msg_data))

            offset = message_end

        return messages

    def peek_type(self, data: bytes) -> MessageType:
        """
        Peek at the message type without full decode.

        Useful for routing decisions before full deserialization.

        Args:
            data: Binary data starting with header

        Returns:
            MessageType from header

        Raises:
            BinaryProtocolError: If header is invalid
        """
        if len(data) < self.HEADER_SIZE:
            raise BinaryProtocolError(
                f"Data too short to peek: {len(data)} < {self.HEADER_SIZE}"
            )

        try:
            _, msg_type, _ = struct.unpack(
                self.HEADER_FORMAT,
                data[:self.HEADER_SIZE]
            )
            return MessageType(msg_type)
        except ValueError as e:
            raise BinaryProtocolError(f"Invalid message type: {e}") from e

    def get_message_length(self, data: bytes) -> int:
        """
        Get total message length from header.

        Args:
            data: Binary data starting with header

        Returns:
            Total message length (header + payload)

        Raises:
            BinaryProtocolError: If header is invalid
        """
        if len(data) < self.HEADER_SIZE:
            raise BinaryProtocolError(
                f"Data too short: {len(data)} < {self.HEADER_SIZE}"
            )

        _, _, length = struct.unpack(
            self.HEADER_FORMAT,
            data[:self.HEADER_SIZE]
        )
        return self.HEADER_SIZE + length

    def is_valid_header(self, data: bytes) -> bool:
        """
        Check if data starts with a valid header.

        Args:
            data: Binary data to check

        Returns:
            True if header is valid
        """
        if len(data) < self.HEADER_SIZE:
            return False

        try:
            version, msg_type, _ = struct.unpack(
                self.HEADER_FORMAT,
                data[:self.HEADER_SIZE]
            )
            # Check version
            if version != self.VERSION:
                return False
            # Check message type is valid
            MessageType(msg_type)
            return True
        except (struct.error, ValueError):
            return False


__all__ = [
    "BinaryProtocol",
    "BinaryProtocolError",
]
