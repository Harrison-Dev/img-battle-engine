import hashlib
import base64

def generate_frame_id(collection, frame, timestamp, text):
    """Generate a base64 ID for a frame that matches the Go implementation."""
    # Create a unique string combining frame data
    frame_str = f"{collection}_{frame}_{timestamp}_{text}"
    
    # Generate a SHA-256 hash of the string
    hash_obj = hashlib.sha256(frame_str.encode('utf-8'))
    
    # Take first 16 bytes of hash to create UUID-like string
    frame_bytes = hash_obj.digest()[:16]
    
    # Convert to URL-safe base64 and remove padding
    frame_id = base64.urlsafe_b64encode(frame_bytes).decode('ascii').rstrip('=')
    
    print(f"[generate_frame_id] Generated ID for frame {frame}: {frame_id}")
    print(f"[generate_frame_id] Source string: {frame_str}")
    
    return frame_id 