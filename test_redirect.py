import time, httpx
time.sleep(3)

# Test unauthenticated /dashboard → should redirect to /dashboard/login, NOT return JSON
r = httpx.get('http://127.0.0.1:8089/dashboard', follow_redirects=False, timeout=5)
print('Status:', r.status_code)
print('Location:', r.headers.get('location', 'none'))
print('Body snippet:', r.text[:80])

assert r.status_code == 302, f"Expected 302, got {r.status_code}"
assert '/dashboard/login' in r.headers.get('location', ''), "Expected redirect to login"
print('PASS: unauthenticated /dashboard redirects to login')
