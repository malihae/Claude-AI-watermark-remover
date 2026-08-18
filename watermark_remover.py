# backend/watermark_remover.py
import cv2
import numpy as np
from PIL import Image
import piexif
import os
import json
from pathlib import Path
import shutil

class WatermarkRemover:
    def __init__(self):
        self.templates = self._load_templates()
        self.supported_formats = ['.png', '.jpg', '.jpeg', '.webp']
    
    def _load_templates(self):
        """Load template patterns for common AI watermarks."""
        # Since we can't load actual images, we'll use pattern definitions
        templates = {
            'claude': {
                'pattern': 'claude_ai',
                'size': (200, 40),
                'locations': ['bottom-right', 'top-left']
            },
            'gemini': {
                'pattern': 'gemini',
                'size': (150, 30),
                'locations': ['bottom-right']
            },
            'dalle': {
                'pattern': 'dall-e',
                'size': (180, 35),
                'locations': ['bottom-left']
            },
            'midjourney': {
                'pattern': 'midjourney',
                'size': (160, 40),
                'locations': ['bottom-right']
            },
            'stable_diffusion': {
                'pattern': 'stable diffusion',
                'size': (190, 30),
                'locations': ['bottom-right']
            }
        }
        return templates
    
    def detect_watermark(self, image_path):
        """Detect watermark in image using multiple methods."""
        detections = []
        
        # Method 1: Check for text patterns using OCR-like approach
        # (Simplified - in production use Tesseract or similar)
        text_detections = self._detect_text_patterns(image_path)
        detections.extend(text_detections)
        
        # Method 2: Check for common watermark positions
        position_detections = self._detect_by_position(image_path)
        detections.extend(position_detections)
        
        # Method 3: Check EXIF metadata
        metadata = self._check_exif_metadata(image_path)
        if metadata:
            detections.append({
                'type': 'metadata',
                'details': metadata,
                'confidence': 1.0
            })
        
        return detections
    
    def _detect_text_patterns(self, image_path):
        """Detect watermark text patterns using template matching."""
        detections = []
        image = cv2.imread(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Use template matching for each known watermark
        for name, template_info in self.templates.items():
            # Create a template from text pattern
            # In production, use actual template images
            template = self._create_text_template(template_info['pattern'])
            if template is None:
                continue
            
            # Multi-scale template matching
            for scale in [0.8, 0.9, 1.0, 1.1, 1.2]:
                if scale != 1.0:
                    scaled_template = cv2.resize(template, None, fx=scale, fy=scale)
                else:
                    scaled_template = template
                
                result = cv2.matchTemplate(gray, scaled_template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                if max_val > 0.6:  # Confidence threshold
                    h, w = scaled_template.shape
                    detections.append({
                        'type': 'visible',
                        'name': name,
                        'bbox': [max_loc[0], max_loc[1], w, h],
                        'confidence': float(max_val),
                        'method': 'template_matching'
                    })
        
        return detections
    
    def _create_text_template(self, text):
        """Create a simple template from text."""
        # This is a placeholder - in production you'd use actual template images
        # or use OCR-based detection
        template_size = (200, 50)
        template = np.zeros(template_size, dtype=np.uint8)
        cv2.putText(template, text, (10, 35), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, 255, 2)
        return template
    
    def _detect_by_position(self, image_path):
        """Detect watermark by checking common positions."""
        detections = []
        image = cv2.imread(image_path)
        h, w = image.shape[:2]
        
        # Check common watermark positions
        positions = [
            ('bottom-right', (w-300, h-100, 200, 50)),
            ('bottom-left', (0, h-100, 200, 50)),
            ('top-right', (w-300, 0, 200, 50)),
            ('top-left', (0, 0, 200, 50)),
        ]
        
        for name, (x, y, width, height) in positions:
            # Extract region
            region = image[y:y+height, x:x+width]
            if region.size == 0:
                continue
            
            # Check for text in region using simple variance
            gray_region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            variance = np.var(gray_region)
            
            # High variance indicates text or patterns
            if variance > 1000:
                detections.append({
                    'type': 'position',
                    'name': name,
                    'bbox': [x, y, width, height],
                    'confidence': min(1.0, variance / 5000),
                    'method': 'position_detection'
                })
        
        return detections
    
    def _check_exif_metadata(self, image_path):
        """Check EXIF metadata for AI generation tags."""
        try:
            img = Image.open(image_path)
            exif_dict = piexif.load(img.info.get('exif', b''))
            
            metadata = {}
            
            # Check for AI-related tags
            if '0th' in exif_dict:
                desc = exif_dict['0th'].get(306)  # DateTime
                if desc:
                    metadata['datetime'] = desc.decode('utf-8', 'ignore')
            
            # Check for software tags
            if '0th' in exif_dict:
                software = exif_dict['0th'].get(305)
                if software:
                    software_str = software.decode('utf-8', 'ignore')
                    if any(ai in software_str.lower() for ai in ['stable', 'diffusion', 'midjourney', 'dall-e', 'claude']):
                        metadata['software'] = software_str
            
            # Check for user comments
            if 'Exif' in exif_dict:
                comment = exif_dict['Exif'].get(37510)
                if comment:
                    comment_str = comment.decode('utf-8', 'ignore')
                    if 'ai' in comment_str.lower() or 'generated' in comment_str.lower():
                        metadata['comment'] = comment_str
            
            return metadata if metadata else None
            
        except Exception as e:
            return None
    
    def remove_watermark(self, image_path, output_path, method='opencv', mask=None):
        """Remove watermark using inpainting."""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        h, w = image.shape[:2]
        
        # Create mask if not provided
        if mask is None:
            mask = np.zeros((h, w), dtype=np.uint8)
            
            # Try to detect watermark
            detections = self.detect_watermark(image_path)
            
            for detection in detections:
                if detection['type'] in ['visible', 'position']:
                    x, y, wm_w, wm_h = detection['bbox']
                    # Add padding
                    padding = 10
                    x1 = max(0, x - padding)
                    y1 = max(0, y - padding)
                    x2 = min(w, x + wm_w + padding)
                    y2 = min(h, y + wm_h + padding)
                    mask[y1:y2, x1:x2] = 255
        
        # Apply inpainting
        if method == 'opencv':
            result = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)
        elif method == 'opencv_ns':
            result = cv2.inpaint(image, mask, 3, cv2.INPAINT_NS)
        else:
            result = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)
        
        # Save result
        cv2.imwrite(output_path, result)
        
        # Also strip metadata
        self._strip_metadata(output_path)
        
        return output_path
    
    def _strip_metadata(self, image_path):
        """Strip AI metadata from image."""
        try:
            img = Image.open(image_path)
            
            # Remove EXIF
            data = list(img.getdata())
            img_without_exif = Image.new(img.mode, img.size)
            img_without_exif.putdata(data)
            
            # Save without metadata
            img_without_exif.save(image_path, quality=95, optimize=True)
            
        except Exception as e:
            print(f"Could not strip metadata: {e}")
    
    def remove_visible_region(self, image_path, output_path, region):
        """Remove watermark from a specific region."""
        image = cv2.imread(image_path)
        x, y, w, h = region
        
        # Create mask for the region
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        mask[y:y+h, x:x+w] = 255
        
        # Inpaint
        result = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)
        cv2.imwrite(output_path, result)
        
        return output_path
    
    def process_batch(self, input_dir, output_dir, method='opencv'):
        """Process all images in a directory."""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        results = []
        for file_path in input_path.iterdir():
            if file_path.suffix.lower() in self.supported_formats:
                try:
                    out_file = output_path / file_path.name
                    self.remove_watermark(str(file_path), str(out_file), method)
                    results.append({
                        'file': file_path.name,
                        'status': 'success',
                        'output': str(out_file)
                    })
                except Exception as e:
                    results.append({
                        'file': file_path.name,
                        'status': 'error',
                        'error': str(e)
                    })
        
        return results
