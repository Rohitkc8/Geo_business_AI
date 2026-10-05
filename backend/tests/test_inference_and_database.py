import pandas as pd

import db.database as database
from explainability import explain_business_to_land, explain_land_to_business


def test_trained_models_return_numeric_scores_and_explanations():
    features = pd.DataFrame([{"population": 1000, "population_density": 1000, "residential_density": 250, "road_density": 10, "distance_to_major_road": 100, "school_count": 1, "college_count": 0, "hospital_count": 1, "bus_stop_count": 2}])
    land = explain_land_to_business(features)
    business = explain_business_to_land(features)
    assert land and 0 <= land[0]["score_percent"] <= 100
    assert isinstance(business["predicted_demand_score"], float)


def test_database_session_is_closed(monkeypatch):
    class Session:
        closed = False
        def close(self): self.closed = True
    session = Session()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    dependency = database.get_db()
    assert next(dependency) is session
    dependency.close()
    assert session.closed
