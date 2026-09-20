import os
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

# In app.js, make fetch calls use getApiUrl
app_js = app_js.replace("fetch('/api/recognize/url'", "fetch(getApiUrl('/api/recognize/url')")
app_js = app_js.replace("fetch('/api/recognize/file'", "fetch(getApiUrl('/api/recognize/file')")
app_js = app_js.replace("fetch('/api/recognize/mic'", "fetch(getApiUrl('/api/recognize/mic')")

# Replace icon references with inlined data URI
html = html.replace('href="assets/icon.png"', f'href="{icon_data_uri}"')
html = html.replace('src="assets/icon.png"', f'src="{icon_data_uri}"')

# Inline CSS and mobile-specific app overrides
mobile_css = """
<style>
/* Hide the 'Get APK' download button ONLY inside the APK application */
#btnDirectDownloadApk {
  display: none !important;
}
#systemBadge {
  cursor: pointer;
}
</style>
"""
html = html.replace('<link rel="stylesheet" href="css/styles.css">', f'<style>\n{css}\n</style>\n{mobile_css}')

# Mobile helper definition before app logic
helper_script = """
<script>
window.SONICAM_IS_MOBILE_APP = true;
window.SONICAM_BACKEND_URL = window.SONICAM_BACKEND_URL || 'https://mohammed-ashraf-shaik-sonicam.hf.space';
function getApiUrl(endpoint) {
    var base = window.SONICAM_BACKEND_URL || 'https://mohammed-ashraf-shaik-sonicam.hf.space';
    if (base) {
        return base.replace(/\\/+$/, '') + endpoint;
    }
    return endpoint;
}
function triggerServerSettings() {
    if (window.ReactNativeWebView) {
        window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'OPEN_SERVER_SETTINGS' }));
    }
}
document.addEventListener('DOMContentLoaded', function() {
    var badge = document.getElementById('systemBadge');
    if (badge) {
        badge.addEventListener('click', triggerServerSettings);
    }
    var brand = document.querySelector('.brand-group');
    if (brand) {
        brand.addEventListener('click', triggerServerSettings);
    }
});
</script>
"""

# Inline JS
html = html.replace('<script src="js/visualizer.js"></script>', '')
html = html.replace(
    '<script src="js/app.js"></script>',
    f'{helper_script}\n<script>\n{vis}\n\n{app_js}\n</script>'
)

# Export as JS module
js_module = f"export const BUNDLED_HTML = {json.dumps(html)};\n"

output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write(js_module)

print(f"Bundle successfully created: {output_path} ({len(js_module)} bytes)")
