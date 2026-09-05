from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import sys
import os

class NoCacheHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    root_dir = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else '/home/mohammad/project/fitsho'
    os.chdir(root_dir)
    server_address = ('0.0.0.0', port)
    httpd = ThreadingHTTPServer(server_address, NoCacheHTTPRequestHandler)
    print(f"Serving {root_dir} on 0.0.0.0:{port} with Threading and No-Cache headers...")
    httpd.serve_forever()
