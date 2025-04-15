import random
import asyncio
import ssl

BLOCKED = [line.rstrip().encode() for line in open('hosts.txt', 'r', encoding='utf-8')]
TASKS = []

async def main(host, port):
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_3
    ssl_context.set_ciphers('TLS_AES_128_GCM_SHA256:TLS_CHacha20_poly1305_sha256:TLS_AES_256_GCM_SHA384')

    server = await asyncio.start_server(new_conn, host, port, ssl=ssl_context)
    print(f"Server started on {host}:{port}")
    await server.serve_forever()

async def pipe(reader, writer):
    try:
        while not reader.at_eof() and not writer.is_closing():
            data = await reader.read(750)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    except Exception as e:
        print(f"Pipe error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()

async def new_conn(local_reader, local_writer):
    try:
        http_data = await local_reader.read(750)

        try:
            type, target = http_data.split(b"\r\n")[0].split(b" ")[0:2]
            host, port = target.split(b":")
            print(f'received CONNECT request for {host.decode()}:{port.decode()}')
        except:
            local_writer.close()
            return

        if type != b"CONNECT":
            local_writer.close()
            return

        local_writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        await local_writer.drain()

        try:
            remote_reader, remote_writer = await asyncio.open_connection(host, port)
        except:
            local_writer.close()
            return

        if port == b'443':
            await fragment_data(local_reader, remote_writer)

        task1 = asyncio.create_task(pipe(local_reader, remote_writer))
        task2 = asyncio.create_task(pipe(remote_reader, local_writer))
        TASKS.append(task1)
        TASKS.append(task2)

        await asyncio.gather(task1, task2)
    finally:
        local_writer.close()
        await local_writer.wait_closed()

async def fragment_data(local_reader, remote_writer):
    head = await local_reader.read(5)
    data = await local_reader.read(750)
    if not data or any(site in data for site in BLOCKED):
        return
    # print(f'received data with header: {head} and data[1:150]: {data}')
    parts = []

    if all([data.find(site) == -1 for site in BLOCKED]):
        remote_writer.write(head + data)
        await remote_writer.drain()
        return

    while data:
        part_len = random.randint(1, len(data))
        parts.append(bytes.fromhex("1603") + bytes([random.randint(0, 255)]) + part_len.to_bytes(2, byteorder='big') + data[:part_len])
        data = data[part_len:]
        print(f'received data from server')
    remote_writer.write(b''.join(parts))
    await remote_writer.drain()

asyncio.run(main(host='127.0.0.1', port=8881))