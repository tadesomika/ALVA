import os
import asyncio
import httpx
from aiofiles import open as aio_open

# File input yang berisi daftar IP dan port
file_input = "autoscan/rawProxyList.txt"
active_file = "autoscan/active.txt"
dead_file = "autoscan/dead.txt"

# Hapus isi file setiap kali script dijalankan ulang
async def clear_file(filepath):
    """Menghapus isi file sebelum menulis data baru"""
    async with aio_open(filepath, 'w') as f:
        await f.write("")

async def check_proxy(ip, port, country, organization, active_cache, dead_cache):
    """Mengecek apakah proxy aktif atau tidak menggunakan dua metode: direct request & Cloudflare API"""

    # Cek proxy langsung
    proxy_url = f"http://{ip}:{port}"
    result = f"{ip},{port},{country},{organization}"

    try:
        transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
        async with httpx.AsyncClient(transport=transport, timeout=5) as client:
            response = await client.get("http://detectportal.firefox.com/success.txt")

            server_header = response.headers.get("server", "").lower()
            status_code = response.status_code

            if server_header == "cloudflare" and status_code == 400:
                if result not in active_cache:
                    async with aio_open(active_file, 'a') as f:
                        await f.write(result + '\n')
                    active_cache.add(result)
                print(f"[✅ AKTIF] {result}")
                return True

    except (httpx.RequestError, httpx.ProxyError, httpx.ConnectTimeout, httpx.ConnectError):
        pass  # Lanjutkan pengecekan dengan API jika gagal

    # Cek proxy menggunakan API eksternal (Cloudflare)
    api_url = f"https://p01--boiling-frame--kw6dd7bjv2nr.code.run/check?ip={ip}&host=speed.cloudflare.com&port={port}&tls=true"
    
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(api_url)
            data = response.json() if response.status_code == 200 else {}

            if data.get("status") == "active":
                if result not in active_cache:
                    async with aio_open(active_file, 'a') as f:
                        await f.write(result + '\n')
                    active_cache.add(result)
                print(f"[✅ AKTIF] {result} (via API)")
                return True

    except (httpx.RequestError, httpx.TimeoutException):
        pass  # Jika API gagal, anggap proxy tidak aktif

    # Jika sampai di sini berarti proxy gagal
    if result not in dead_cache:
        async with aio_open(dead_file, 'a') as f:
            await f.write(result + '\n')
        dead_cache.add(result)
    print(f"[❌ TIDAK AKTIF] {result}")
    return False

async def process_proxies(filename, max_workers=300):
    """Membaca file dan memeriksa setiap proxy secara async"""
    if not os.path.exists(filename):
        print(f"File '{filename}' tidak ditemukan.")
        return

    # Hapus isi file active.txt dan dead.txt setiap kali dijalankan ulang
    await clear_file(active_file)
    await clear_file(dead_file)

    active_cache = set()
    dead_cache = set()

    tasks = []
    async with aio_open(filename, 'r') as file:
        async for line in file:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                ip = parts[0]
                try:
                    port = int(parts[1])
                except ValueError:
                    print(f"[ERROR] Port tidak valid: {parts[1]}")
                    continue

                country = parts[2] if len(parts) > 2 else "Unknown"
                organization = parts[3] if len(parts) > 3 else "Unknown"

                tasks.append(check_proxy(ip, port, country, organization, active_cache, dead_cache))

    # Batasi jumlah task yang berjalan bersamaan
    sem = asyncio.Semaphore(max_workers)

    async def sem_task(task):
        async with sem:
            return await task

    await asyncio.gather(*(sem_task(task) for task in tasks))

# Jalankan pengecekan proxy
if __name__ == "__main__":
    asyncio.run(process_proxies(file_input))
