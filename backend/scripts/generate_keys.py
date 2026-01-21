"""RSA key pair generation script for JWT signing.

Usage:
    python scripts/generate_keys.py
    
Generates:
    - keys/private.pem: RSA private key for signing tokens
    - keys/public.pem: RSA public key for verifying tokens
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def generate_keys(output_dir: str = "keys") -> None:
    """Generate RSA key pair for JWT signing."""
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        print("Error: cryptography package is required.")
        print("Install it with: pip install cryptography")
        sys.exit(1)

    # Create output directory
    keys_dir = Path(output_dir)
    keys_dir.mkdir(parents=True, exist_ok=True)

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Serialize public key
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Write keys to files
    private_path = keys_dir / "private.pem"
    public_path = keys_dir / "public.pem"

    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    # Set restrictive permissions on private key
    os.chmod(private_path, 0o600)
    os.chmod(public_path, 0o644)

    print(f"Generated RSA key pair:")
    print(f"  Private key: {private_path}")
    print(f"  Public key:  {public_path}")
    print()
    print("IMPORTANT: Keep the private key secure and never commit it to git!")
    print("The keys/ directory should be in .gitignore")


if __name__ == "__main__":
    generate_keys()
