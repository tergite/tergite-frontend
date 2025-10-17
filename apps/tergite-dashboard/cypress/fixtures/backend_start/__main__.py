"""Module to wrap uvicorn in frozen time"""
import os
from datetime import datetime
from freezegun import freeze_time
from uvicorn.main import main as uvicorn_main

def main():
    """A wrapper to freeze time then call uvicorn
    
    It is invoked on the command line just like uvicorn would be invoked i.e. `python -m uvicorn`
    """
    current_date = os.getenv("CURRENT_DATE", "2025-10-01T00:00:00.000Z")

    with freeze_time(datetime.fromisoformat(current_date)):
        uvicorn_main()

if __name__ == "__main__":
    main()