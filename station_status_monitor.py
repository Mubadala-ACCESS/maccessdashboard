#!/usr/bin/env python3
import time
from datetime import datetime, timedelta
from pymongo import MongoClient


# ----------------- CONFIGURATION -----------------
MONGO_URI       = "mongodb://10.224.41.205:27017/"
DB_NAME         = "all_stations_db"
STALE_THRESHOLD = timedelta(hours=6)


# Station types to check
STATION_TYPES = ["IoTBox", "Meteorological", "Buoy", "Fidas_Palas"]


# station_num → (collection name, timestamp field)
SPECIAL_STATIONS = {
    5463: ("f1_meteostation", "Timestamp"),
     100: ("fidas_nyuad",     "datetime"),
    8394: ("buoy_01",         "datetime"),
}


# ----------------- MAIN MONITOR -----------------
def check_and_update_status():
    client = MongoClient(MONGO_URI)
    db     = client[DB_NAME]
    now    = datetime.utcnow()


    # Get all stations of the specified types
    stations = db.stations_info.find({"type": {"$in": STATION_TYPES}})


    for station_info in stations:
        sn = station_info.get("station_num")
        if not sn:
            continue

        current_status = station_info.get("status", "Active")

        # Determine collection name and timestamp field
        coll_name, ts_field = SPECIAL_STATIONS.get(sn, (f"station{sn}", "datetime"))


        try:
            # Fetch latest record
            rec = db[coll_name].find_one(sort=[(ts_field, -1)])


            if not rec:
                print(f"[{now}] Station {sn}: No records found")
                continue


            rec_ts = rec.get(ts_field)


            if not isinstance(rec_ts, datetime):
                print(f"[{now}] Station {sn}: Missing/invalid timestamp field '{ts_field}'")
                continue


            # Check if data is stale (older than 6 hours)
            age = now - rec_ts
            if age > STALE_THRESHOLD:
                # Update status to 'Maintenance' only if not already in Maintenance
                if current_status != "Maintenance":
                    db.stations_info.update_one(
                        {"station_num": sn},
                        {"$set": {"status": "Maintenance"}}
                    )
                    print(f"[{now}] Station {sn}: Status updated to 'Maintenance' (last data: {rec_ts})")
                else:
                    print(f"[{now}] Station {sn}: Still in Maintenance (last data: {rec_ts})")
            else:
                # Data is fresh - update to 'Active' if currently in Maintenance
                if current_status == "Maintenance":
                    db.stations_info.update_one(
                        {"station_num": sn},
                        {"$set": {"status": "Active"}}
                    )
                    print(f"[{now}] Station {sn}: Status restored to 'Active' (last data: {rec_ts})")
                else:
                    print(f"[{now}] Station {sn}: OK (last data: {rec_ts})")


        except Exception as e:
            print(f"[{now}] Station {sn}: Error - {e}")


    client.close()


if __name__ == "__main__":
    print("Starting station status monitor (checks every 1 hour)…")
    while True:
        check_and_update_status()
        time.sleep(3600)
