from sqlalchemy.orm import Session
import sqlalchemy
from sqlalchemy import func
from db.models import Business, Hospital, AnalysisResult, Road
from geoalchemy2.elements import WKTElement

def get_nearby_businesses(db: Session, lat: float, lon: float, radius_meters: float = 500.0, category: str = None):
    """
    Radius search: Finds all businesses within `radius_meters` of a given (lat, lon).
    ST_DWithin requires Geography type for accurate meter measurements or ST_Transform.
    Assuming SRID 4326, we cast to geography for distance in meters.
    """
    point = WKTElement(f'POINT({lon} {lat})', srid=4326)
    
    query = db.query(Business).filter(
        func.ST_DWithin(
            func.cast(Business.geom, sqlalchemy.types.UserDefinedType("geography")),
            func.cast(point, sqlalchemy.types.UserDefinedType("geography")),
            radius_meters
        )
    )
    if category:
        query = query.filter(Business.category == category)
        
    return query.all()

def get_nearest_hospital(db: Session, lat: float, lon: float):
    """
    Nearest POI: Finds the closest hospital using KNN spatial query.
    """
    point = WKTElement(f'POINT({lon} {lat})', srid=4326)
    
    # Use the <-> operator for nearest neighbor distances
    nearest = db.query(Hospital).order_by(
        Hospital.geom.distance_centroid(point)
    ).first()
    
    return nearest

def get_candidate_locations(db: Session, bounding_box_wkt: str, min_score: float = 10000.0):
    """
    Geographic Filtering: Finds candidate locations from AnalysisResults inside a bounding box.
    bounding_box_wkt should be a POLYGON WKT.
    """
    polygon = WKTElement(bounding_box_wkt, srid=4326)
    
    candidates = db.query(AnalysisResult).filter(
        func.ST_Intersects(AnalysisResult.geom, polygon),
        AnalysisResult.predicted_score >= min_score
    ).all()
    
    return candidates

def get_distance_to_nearest_major_road(db: Session, lat: float, lon: float):
    """
    Spatial Measurement: Finds the shortest distance in meters to a major road.
    """
    point = WKTElement(f'POINT({lon} {lat})', srid=4326)
    
    # KNN to find nearest road, then ST_Distance on geography to get meters
    nearest_road = db.query(Road, func.ST_Distance(
        func.cast(Road.geom, sqlalchemy.types.UserDefinedType("geography")),
        func.cast(point, sqlalchemy.types.UserDefinedType("geography"))
    ).label('distance')).order_by(
        Road.geom.distance_centroid(point)
    ).first()
    
    return nearest_road.distance if nearest_road else None
