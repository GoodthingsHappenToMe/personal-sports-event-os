import json
import sqlite3
from pathlib import Path
from ..models import assert_model, canonical

class Store:
    """Single canonical working JSON in SQLite; typed read-only SQL views.

    JSON files are explicit imports/exports, never a second live data source.
    """
    def __init__(self,path):
        self.path=Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        con=sqlite3.connect(self.path)
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("CREATE TABLE IF NOT EXISTS working_state (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL CHECK(json_valid(data)))")
        for group in ("sessions","seating","prices","inventory","products","rules","tasks","decisions"):
            from ..models.schema import SCHEMA
            props=SCHEMA["properties"][group]["items"]["properties"]
            columns=", ".join(f"json_extract(j.value, '$.{key}') AS {key}" for key in props)
            if group=="seating":
                columns+=", json_extract(j.value,'$.physical_capacity')-json_extract(j.value,'$.functional_hold')-json_extract(j.value,'$.broadcast_hold')-json_extract(j.value,'$.free_rights')-json_extract(j.value,'$.other_hold') AS sellable_capacity"
            if group=="products":
                columns+=", (SELECT SUM(json_extract(c.value,'$.ticket_quantity')) FROM json_each(j.value,'$.included_sessions') c) AS ticket_quantity"
            con.execute(f"CREATE VIEW IF NOT EXISTS {group} AS SELECT {columns} FROM working_state w,json_each(w.data,'$.{group}') j")
        columns=", ".join(f"json_extract(data, '$.event.{key}') AS {key}" for key in SCHEMA["properties"]["event"]["properties"])
        con.execute(f"CREATE VIEW IF NOT EXISTS event AS SELECT {columns} FROM working_state")
        return con

    def save(self,data):
        assert_model(data)
        with self.connect() as con:
            con.execute("INSERT INTO working_state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",(canonical(data),))

    def load(self):
        if not self.path.exists():
            raise ValueError("工作库不存在；先运行 demo 或 load")
        with self.connect() as con:
            row=con.execute("SELECT data FROM working_state WHERE id=1").fetchone()
        if not row:raise ValueError("工作库为空")
        return assert_model(json.loads(row[0]))
