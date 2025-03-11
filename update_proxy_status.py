import requests
import csv
import shutil
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

def check_proxy_single(ip, port, api_url_template):
    """
    Mengecek satu proxy menggunakan API.
    """
    try:
        # Format URL API untuk satu proxy
        api_url = api_url_template.format(ip=ip, port=port)
        print(f"Mengakses API: {api_url}")

        # Kirim request ke API
        response = requests.get(api_url, timeout=60)
        response.raise_for_status()
        data = response.json()

        # Ambil status proxyip
        status = data[0].get("proxyip", False)
        if status:
            print(f"{ip}:{port} [✅ AKTIF]")
            return (ip, port, None)  # Format: (ip, port, None)
        else:
            print(f"{ip}:{port} [❌ TIDAK AKTIF]")
            return (None, None, f"{ip}:{port} [❌ TIDAK AKTIF]")  # Format: (None, None, error_message)
    except requests.exceptions.RequestException as e:
        error_message = f"Error checking {ip}:{port}: {e}"
        print(error_message)
        return (None, None, error_message)
    except ValueError as ve:
        error_message = f"Error parsing JSON for {ip}:{port}: {ve}"
        print(error_message)
        return (None, None, error_message)

def main():
    input_file = os.getenv('IP_FILE', 'active.txt')
    output_file = 'active.txt'
    error_file = 'dead.txt'
    api_url_template = os.getenv('API_URL', 'https://lodd.vercel.app/{ip}:{port}')

    alive_proxies = []  # Menyimpan proxy yang aktif dengan format [ip, port, cc, isp]
    error_logs = []  # Menyimpan pesan error

    try:
        with open(input_file, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
        print(f"Memproses {len(rows)} baris dari file input.")
    except FileNotFoundError:
        print(f"File {input_file} tidak ditemukan.")
        return

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for row in rows:
            if len(row) >= 2:
                ip, port = row[0].strip(), row[1].strip()
                futures.append(executor.submit(check_proxy_single, ip, port, api_url_template))

        for future in as_completed(futures):
            ip, port, error = future.result()
            if ip and port:
                # Cari baris yang sesuai dari file input
                for row in rows:
                    if row[0].strip() == ip and row[1].strip() == port:
                        alive_proxies.append(row)  # Simpan seluruh baris (ip, port, cc, isp)
                        break
            if error:
                error_logs.append(error)

    # Tulis proxy yang aktif ke file output
    try:
        with open(output_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(alive_proxies)
        print(f"File output {output_file} telah diperbarui.")
    except Exception as e:
        print(f"Error menulis ke {output_file}: {e}")
        return

    # Tulis error ke file error.txt
    if error_logs:
        try:
            with open(error_file, "w") as f:
                for error in error_logs:
                    f.write(error + "\n")
            print(f"Beberapa error telah dicatat di {error_file}.")
        except Exception as e:
            print(f"Error menulis ke {error_file}: {e}")
            return

    # Ganti file input dengan file output
    try:
        shutil.move(output_file, input_file)
        print(f"{input_file} telah diperbarui dengan proxy yang [✅ AKTIF].")
    except Exception as e:
        print(f"Error menggantikan {input_file}: {e}")

if __name__ == "__main__":
    main()
