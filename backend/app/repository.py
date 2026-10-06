import os
from datetime import datetime,timezone
from .models import Ticket
from .data import make_tickets
class Repository:
    def __init__(self):
        self.mode="memory"; self.collection=None; uri=os.getenv("MONGODB_URI","").strip()
        if uri:
            try:
                from pymongo import MongoClient
                client=MongoClient(uri,serverSelectionTimeoutMS=1200);client.admin.command("ping")
                self.collection=client[os.getenv("MONGODB_DATABASE","nexus")]["tickets"];self.mode="mongodb"
            except Exception: self.collection=None
        if self.collection is None:self.items={t.ticket_id:t for t in make_tickets()}
        elif self.collection.count_documents({})==0:self.collection.insert_many([t.model_dump() for t in make_tickets()])
    def all(self):
        if self.collection is not None:return [Ticket(**{k:v for k,v in d.items() if k!="_id"}) for d in self.collection.find().sort("created_at",-1)]
        return sorted(self.items.values(),key=lambda x:x.created_at,reverse=True)
    def get(self,id):
        if self.collection is not None:
            d=self.collection.find_one({"ticket_id":id});return Ticket(**{k:v for k,v in d.items() if k!="_id"}) if d else None
        return self.items.get(id)
    def save(self,t):
        t.updated_at=datetime.now(timezone.utc)
        if self.collection is not None:self.collection.replace_one({"ticket_id":t.ticket_id},t.model_dump(),upsert=True)
        else:self.items[t.ticket_id]=t
        return t
repo=Repository()
