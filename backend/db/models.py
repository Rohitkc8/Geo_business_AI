from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from geoalchemy2 import Geometry
from db.database import Base
from datetime import datetime

class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    geom = Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=True))
    created_at = Column(DateTime, default=datetime.utcnow)

class Business(Base):
    __tablename__ = "businesses"
    id = Column(Integer, primary_key=True, index=True)
    osm_id = Column(String, unique=True, index=True)
    name = Column(String)
    category = Column(String, index=True)  # e.g., 'restaurant', 'pharmacy'
    geom = Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=True))

class Road(Base):
    __tablename__ = "roads"
    id = Column(Integer, primary_key=True, index=True)
    osm_id = Column(String, unique=True)
    highway_type = Column(String, index=True) # e.g., 'primary', 'secondary'
    geom = Column(Geometry(geometry_type='LINESTRING', srid=4326, spatial_index=True))

class School(Base):
    __tablename__ = "schools"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    geom = Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=True))

class College(Base):
    __tablename__ = "colleges"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    geom = Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=True))

class Hospital(Base):
    __tablename__ = "hospitals"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    geom = Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=True))

class PopulationGrid(Base):
    __tablename__ = "population_grids"
    id = Column(Integer, primary_key=True, index=True)
    population = Column(Float)
    density = Column(Float)
    geom = Column(Geometry(geometry_type='POLYGON', srid=4326, spatial_index=True))

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(Integer, primary_key=True, index=True)
    business_type = Column(String, index=True)
    predicted_score = Column(Float)
    geom = Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=True))
    created_at = Column(DateTime, default=datetime.utcnow)
