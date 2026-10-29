# Production TLS Certificates Directory

In production (Stage D), mount or copy your valid TLS certificates here:
- `fullchain.pem`: Full certificate chain issued by your CA (e.g. Let's Encrypt / Certbot).
- `privkey.pem`: Corresponding private key.

Strict TLS 1.3 is enforced by `nginx/nginx.prod.conf`.
Do not commit actual production keys or certs to version control.
