class Scheduler:
    """
    Placeholder scheduler.
    Will later manage:
      - run queue
      - fairness
      - resource arbitration
    """

    def submit(self, run_request: dict) -> dict:
        """
        Accept a run request and return execution metadata.
        """
        return {
            "status": "accepted",
            "run_id": "dummy-run-id",
        }
