import json
from channels.generic.websocket import AsyncWebsocketConsumer

class SyncConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'sync_group'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Client can send ack if needed
        pass

    async def send_update(self, event):
        # Send message to WebSocket client
        await self.send(text_data=json.dumps({
            'type': event['update_type'],
            'data_type': event.get('data_type'),
            'message': event['message']
        }))
