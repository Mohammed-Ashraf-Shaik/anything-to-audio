import os
import re
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

index_path = ROOT / "frontend" / "index.html"
css_path = ROOT / "frontend" / "css" / "styles.css"
vis_path = ROOT / "frontend" / "js" / "visualizer.js"
app_path = ROOT / "frontend" / "js" / "app.js"
icon_path = ROOT / "mobile" / "assets" / "icon_192.png"
output_path = ROOT / "mobile" / "assets" / "bundled_html.js"

with open(index_path, "r", encoding="utf-8") as f:
    html = f.read()

with open(css_path, "r", encoding="utf-8") as f:
    css = f.read()

with open(vis_path, "r", encoding="utf-8") as f:
    vis = f.read()

with open(app_path, "r", encoding="utf-8") as f:
    app_js = f.read()

with open(icon_path, "rb") as f:
    icon_b64 = base64.b64encode(f.read()).decode("utf-8")
icon_data_uri = f"data:image/png;base64,{icon_b64}"

# 1. Ensure fetch calls use getApiUrl
app_js = app_js.replace("fetch('/api/recognize/url'", "fetch(getApiUrl('/api/recognize/url')")
app_js = app_js.replace("fetch('/api/recognize/file'", "fetch(getApiUrl('/api/recognize/file')")
app_js = app_js.replace("fetch('/api/recognize/mic'", "fetch(getApiUrl('/api/recognize/mic')")

# 2. Replace icon references with inlined data URI
html = html.replace('href="assets/icon.png"', f'href="{icon_data_uri}"')
html = html.replace('src="assets/icon.png"', f'src="{icon_data_uri}"')

# 3. Surgically remove all 'Download APK' elements from the bundled HTML for mobile
html = re.sub(r'<div class="hero-apk-badge-wrapper">.*?</div>\s*', '', html, flags=re.DOTALL)
html = re.sub(r'<a\s+[^>]*id="btnDirectDownloadApk"[^>]*>.*?</a>\s*', '', html, flags=re.DOTALL)
html = re.sub(r'<a\s+[^>]*href="[^"]*SonicAM\.apk"[^>]*>.*?</a>\s*', '', html, flags=re.DOTALL)

# 4. Clean file input accept attribute for Android WebView native file picker
html = html.replace(
    'accept="video/*,audio/*,.mp4,.mkv,.mov,.avi,.webm,.mp3,.wav,.m4a,.flac,.ogg,.aac"',
    'accept="audio/*,video/*"'
)

# 5. Inline CSS and mobile-specific app overrides
mobile_css = """
<style>
/* Completely hide and eliminate all APK download elements inside the APK application */
#btnDirectDownloadApk,
.hero-apk-badge-wrapper,
.hero-apk-badge,
a[href*="SonicAM.apk"],
.footer-link[href*="SonicAM.apk"] {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
  max-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden !important;
  pointer-events: none !important;
}
</style>
"""
html = html.replace('<link rel="stylesheet" href="css/styles.css">', f'<style>\n{css}\n</style>\n{mobile_css}')

# 6. Mobile helper definition before app logic - Exclusively routes to 24/7 Vercel Cloud Server
helper_script = """
<script>
window.SONICAM_IS_MOBILE_APP = true;
window.SONICAM_BACKEND_URL = 'https://anything-to-audio-am.vercel.app';
function getApiUrl(endpoint) {
    var base = window.SONICAM_BACKEND_URL || 'https://anything-to-audio-am.vercel.app';
    if (base) {
        return base.replace(/\\/+$/, '') + endpoint;
    }
    return endpoint;
}

// Ensure body has mobile class and any leftover APK elements are purged
(function() {
    function purgeApk() {
        if (document.body) document.body.classList.add('is-mobile-app');
        var bad = document.querySelectorAll('#btnDirectDownloadApk, .hero-apk-badge-wrapper, .hero-apk-badge, a[href*="SonicAM.apk"], .footer-link[href*="SonicAM.apk"]');
        bad.forEach(function(el) {
            if (el && el.parentNode) el.parentNode.removeChild(el);
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', purgeApk);
    } else {
        purgeApk();
    }
    setTimeout(purgeApk, 200);
})();
</script>
"""

# 7. Inline JS
html = html.replace('<script src="js/visualizer.js"></script>', '')
html = html.replace(
    '<script src="js/app.js"></script>',
    f'{helper_script}\n<script>\n{vis}\n\n{app_js}\n</script>'
)

# 8. Export as JS module
js_module = f"export const BUNDLED_HTML = {json.dumps(html)};\n"

output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write(js_module)

print(f"Bundle successfully created: {output_path} ({len(js_module)} bytes)")
