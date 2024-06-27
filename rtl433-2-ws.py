import asyncio
import json
import os
import websockets
import tomllib

WEBSOCKET_HOST = '0.0.0.0'
# 'localhost' -> only this machine can connect
# '0.0.0.0' -> all machines from network can connect
WEBSOCKET_PORT = 443 # HTTPS port
WEBSOCKET_PASSWORD = ''

connected_clients = set()

async def authenticate(websocket):
    if not WEBSOCKET_PASSWORD or len(WEBSOCKET_PASSWORD) == 0:
        return True
    
    try:
        message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        data = json.loads(message)
        if data.get('type') == 'auth' and data.get('password') == WEBSOCKET_PASSWORD:
            return True
    except (asyncio.TimeoutError, json.JSONDecodeError):
        pass
    return False

async def run_rtl_433():
    process = await asyncio.create_subprocess_exec(
        './rtl_433/rtl_433.exe', '-F', 'json',
        # '-f', '433.92M', # Default Frequency
        # '-f', '868M',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        
        try:
            data = json.loads(line.decode().strip())
            
            await broadcast(json.dumps(data))
        except json.JSONDecodeError:
            print(f"Failed to parse JSON: {line.decode().strip()}")

async def broadcast(message):
    if connected_clients:
        await asyncio.gather(
            *[client.send(message) for client in connected_clients]
        )

async def handle_client(websocket, path):
    if not await authenticate(websocket):
        await websocket.close(1008, "authentication failed")
        return

    try:
        connected_clients.add(websocket)
        print(f"New client connected. Total clients: {len(connected_clients)}")
        
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)
        print(f"Client disconnected. Total clients: {len(connected_clients)}")

async def main():

    global WEBSOCKET_HOST,WEBSOCKET_PORT,WEBSOCKET_PASSWORD

    if os.path.exists("config.toml"):
        with open("config.toml", "rb") as f:
            config = tomllib.load(f)
            if (host := config["host"]) is not None:
                WEBSOCKET_HOST = host
            if (port := config["port"]) is not None:
                WEBSOCKET_PORT = port
            if (password := config["password"]) is not None:
                WEBSOCKET_PASSWORD = password

    server = await websockets.serve(handle_client, WEBSOCKET_HOST, WEBSOCKET_PORT)
    
    rtl_433_task = asyncio.create_task(run_rtl_433())
    
    print("Server started. Waiting for connections...")
    
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())