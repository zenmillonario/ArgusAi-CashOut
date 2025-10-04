#!/usr/bin/env python3
"""
Android App Icon Generator
Generates all required Android app icon sizes from a source image.
"""

import os
from PIL import Image, ImageFilter, ImageEnhance
import sys

def create_rounded_icon(image, size):
    """Create a rounded app icon with proper Android styling"""
    # Resize the image to the target size
    img = image.copy()
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    
    # Create a circular mask
    mask = Image.new('L', (size, size), 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    
    # Create rounded corners (Android adaptive icon style)
    corner_radius = int(size * 0.1)  # 10% corner radius
    draw.rounded_rectangle([(0, 0), (size, size)], corner_radius, fill=255)
    
    # Apply the mask
    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    img = img.convert("RGBA")
    output.paste(img, mask=mask)
    
    return output

def enhance_image_for_icon(image):
    """Enhance image contrast and sharpness for better icon appearance"""
    # Convert to RGB if necessary
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Enhance contrast slightly
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.2)
    
    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1.3)
    
    return image

def generate_android_icons(source_path, output_dir):
    """Generate all required Android app icon sizes"""
    
    # Android icon sizes (in pixels)
    icon_sizes = {
        'mipmap-mdpi': 48,
        'mipmap-hdpi': 72,
        'mipmap-xhdpi': 96,
        'mipmap-xxhdpi': 144,
        'mipmap-xxxhdpi': 192
    }
    
    # Notification icon sizes (smaller, simpler)
    notification_sizes = {
        'drawable-mdpi': 24,
        'drawable-hdpi': 36,
        'drawable-xhdpi': 48,
        'drawable-xxhdpi': 72,
        'drawable-xxxhdpi': 96
    }
    
    try:
        # Load and enhance the source image
        source_image = Image.open(source_path)
        enhanced_image = enhance_image_for_icon(source_image)
        
        print(f"Source image loaded: {source_image.size}")
        print(f"Generating Android app icons...")
        
        # Generate main app icons
        for density, size in icon_sizes.items():
            # Create directory if it doesn't exist
            dir_path = os.path.join(output_dir, 'android', 'app', 'src', 'main', 'res', density)
            os.makedirs(dir_path, exist_ok=True)
            
            # Create rounded icon
            icon = create_rounded_icon(enhanced_image, size)
            
            # Save as PNG
            icon_path = os.path.join(dir_path, 'ic_launcher.png')
            icon.save(icon_path, 'PNG', optimize=True)
            print(f"Created {density}/ic_launcher.png ({size}x{size})")
            
            # Also create round icon
            round_icon_path = os.path.join(dir_path, 'ic_launcher_round.png')
            icon.save(round_icon_path, 'PNG', optimize=True)
            print(f"Created {density}/ic_launcher_round.png ({size}x{size})")
        
        # Generate notification icons (simpler, monochrome style)
        print(f"Generating notification icons...")
        for density, size in notification_sizes.items():
            dir_path = os.path.join(output_dir, 'android', 'app', 'src', 'main', 'res', density)
            os.makedirs(dir_path, exist_ok=True)
            
            # Create simple notification icon (just the peacock silhouette)
            notif_icon = enhanced_image.copy()
            notif_icon = notif_icon.resize((size, size), Image.Resampling.LANCZOS)
            
            # Convert to grayscale and enhance for notification
            notif_icon = notif_icon.convert('L')  # Grayscale
            notif_icon = notif_icon.convert('RGBA')
            
            notif_path = os.path.join(dir_path, 'ic_notification.png')
            notif_icon.save(notif_path, 'PNG', optimize=True)
            print(f"Created {density}/ic_notification.png ({size}x{size})")
        
        # Generate large icon for play store (512x512)
        playstore_icon = create_rounded_icon(enhanced_image, 512)
        playstore_path = os.path.join(output_dir, 'playstore_icon.png')
        playstore_icon.save(playstore_path, 'PNG', optimize=True)
        print(f"Created Play Store icon: playstore_icon.png (512x512)")
        
        print(f"✅ All Android icons generated successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error generating icons: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_icons.py <source_image> <output_directory>")
        sys.exit(1)
    
    source_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not os.path.exists(source_path):
        print(f"Error: Source image not found: {source_path}")
        sys.exit(1)
    
    success = generate_android_icons(source_path, output_dir)
    sys.exit(0 if success else 1)