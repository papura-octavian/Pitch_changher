# Icons Directory

Place your application icon file here:

- **icon.ico** - Windows icon file (will be used for Windows executable and installer)
- The icon will be automatically converted to PNG for Linux AppImage

## Icon Requirements

- **Format**: .ico for Windows
- **Recommended sizes**: 16x16, 32x32, 48x48, 256x256 (multi-resolution ICO)
- **For Linux**: The .ico will be automatically converted to PNG 256x256

## How to create an icon

1. Create or find an image (PNG, SVG, etc.)
2. Use an online converter or tool like:
   - https://convertio.co/png-ico/
   - https://www.icoconverter.com/
3. Save as `icon.ico` in this directory
4. The build process will automatically use it

## Note

If no icon is provided, the build will:
- Windows: Use default Windows icon
- Linux: Create a simple placeholder icon

