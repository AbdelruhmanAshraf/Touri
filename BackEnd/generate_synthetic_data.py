import pandas as pd
import random
import os
from pathlib import Path

BASE_DIR = Path("/Users/abdelruhamanelfekky/Desktop/Gen project/Tripmind/BackEnd/data/datasets")

# Ensure directories exist
countries = ["egypt", "saudi_arabia", "qatar", "turkey", "morocco"]
for c in countries:
    (BASE_DIR / c).mkdir(parents=True, exist_ok=True)

# Data templates
data_templates = {
    "saudi_arabia": {
        "cities": ["Riyadh", "Jeddah", "Makkah", "Dammam", "Madinah"],
        "hotel_prefixes": ["Riyadh", "Jeddah", "Desert", "Oasis", "Royal", "Al", "King"],
        "hotel_suffixes": ["Hotel", "Palace", "Resort", "Suites", "Inn"],
        "attraction_types": ["Museum", "Mosque", "Mall", "Desert Camp", "Historical Site"],
        "cuisines": ["Saudi", "Middle Eastern", "International", "Indian", "Lebanese"],
        "transport": ["Uber", "Taxi", "Metro", "Bus", "Private Car"],
        "medical_types": ["Hospital", "Clinic", "Dental Center", "Wellness Resort"],
        "currency": "SAR",
        "price_mult": 1.5
    },
    "qatar": {
        "cities": ["Doha", "Al Rayyan", "Al Wakrah", "Al Khor", "Lusail"],
        "hotel_prefixes": ["Doha", "Gulf", "Pearl", "Desert", "Royal", "Al", "Qatar"],
        "hotel_suffixes": ["Hotel", "Palace", "Resort", "Suites", "Inn", "Tower"],
        "attraction_types": ["Museum", "Souq", "Mall", "Park", "Cultural Village"],
        "cuisines": ["Qatari", "Middle Eastern", "International", "Indian", "Lebanese"],
        "transport": ["Uber", "Karwa Taxi", "Doha Metro", "Bus", "Private Car"],
        "medical_types": ["Hospital", "Clinic", "Dental Center", "Wellness Resort"],
        "currency": "QAR",
        "price_mult": 2.0
    },
    "turkey": {
        "cities": ["Istanbul", "Antalya", "Ankara", "Izmir", "Bursa", "Cappadocia"],
        "hotel_prefixes": ["Istanbul", "Bosphorus", "Ottoman", "Sultan", "Grand", "Anatolian"],
        "hotel_suffixes": ["Hotel", "Palace", "Resort", "Suites", "Inn", "Cave Hotel"],
        "attraction_types": ["Museum", "Mosque", "Bazaar", "Ruins", "Palace"],
        "cuisines": ["Turkish", "Mediterranean", "International", "Seafood", "Middle Eastern"],
        "transport": ["Taxi", "Metro", "Tram", "Bus", "Ferry"],
        "medical_types": ["Hospital", "Hair Transplant Clinic", "Dental Center", "Cosmetic Surgery Center"],
        "currency": "TRY",
        "price_mult": 0.5
    },
    "morocco": {
        "cities": ["Marrakech", "Casablanca", "Fes", "Tangier", "Rabat", "Chefchaouen"],
        "hotel_prefixes": ["Marrakech", "Atlas", "Royal", "Grand", "Sahara", "Moorish"],
        "hotel_suffixes": ["Hotel", "Riad", "Palace", "Resort", "Inn", "Dar"],
        "attraction_types": ["Medina", "Mosque", "Souk", "Palace", "Garden", "Kasbah"],
        "cuisines": ["Moroccan", "Mediterranean", "French", "International", "Seafood"],
        "transport": ["Petit Taxi", "Grand Taxi", "Train", "Bus", "Private Car"],
        "medical_types": ["Hospital", "Clinic", "Dental Center", "Wellness Retreat", "Hammam Spa"],
        "currency": "MAD",
        "price_mult": 0.8
    },
    "egypt": { # Only generating medical centers for Egypt since other data exists
        "cities": ["Cairo", "Alexandria", "Luxor", "Aswan", "Sharm El Sheikh", "Hurghada"],
        "medical_types": ["Hospital", "Clinic", "Dental Center", "Wellness Resort", "Eye Center"],
        "currency": "EGP",
        "price_mult": 1.0
    }
}

def generate_hotels(country):
    template = data_templates[country]
    data = []
    for _ in range(50):
        city = random.choice(template["cities"])
        name = f'{random.choice(template["hotel_prefixes"])} {random.choice(template["hotel_suffixes"])}'
        data.append({
            "Hotel Name": name,
            "City": city,
            "Rating": round(random.uniform(3.0, 5.0), 1),
            "Stars": random.randint(3, 5),
            f"Price ({template['currency']})": int(random.uniform(200, 1500) * template["price_mult"])
        })
    return pd.DataFrame(data)

def generate_attractions(country):
    template = data_templates[country]
    data = []
    for _ in range(50):
        city = random.choice(template["cities"])
        cat = random.choice(template["attraction_types"])
        name = f'{city} {cat}'
        data.append({
            "Attraction": name,
            "City": city,
            "Rating": round(random.uniform(3.5, 5.0), 1),
            "Category": cat
        })
    return pd.DataFrame(data)

def generate_restaurants(country):
    template = data_templates[country]
    data = []
    for _ in range(50):
        city = random.choice(template["cities"])
        cuisine = random.choice(template["cuisines"])
        name = f'{city} {cuisine} Restaurant'
        data.append({
            "Name": name,
            "City": city,
            "User Rating": round(random.uniform(3.0, 5.0), 1),
            "Cuisine": cuisine
        })
    return pd.DataFrame(data)

def generate_transport(country):
    template = data_templates[country]
    data = []
    for _ in range(20):
        city = random.choice(template["cities"])
        ttype = random.choice(template["transport"])
        data.append({
            "City": city,
            "Type": ttype,
            f"Price ({template['currency']})": int(random.uniform(10, 100) * template["price_mult"])
        })
    return pd.DataFrame(data)

def generate_flights(country):
    template = data_templates[country]
    data = []
    for _ in range(20):
        c1 = random.choice(template["cities"])
        c2 = random.choice([c for c in template["cities"] if c != c1])
        if not c2: continue
        data.append({
            "Origin": c1,
            "Destination": c2,
            "Airline": f"{country.title().replace('_', ' ')} Air",
            f"Price ({template['currency']})": int(random.uniform(500, 2000) * template["price_mult"])
        })
    return pd.DataFrame(data)

def generate_medical_centers(country):
    template = data_templates[country]
    data = []
    for _ in range(30):
        city = random.choice(template["cities"])
        mtype = random.choice(template["medical_types"])
        name = f'{city} International {mtype}'
        data.append({
            "Name": name,
            "City": city,
            "Type": mtype,
            "Rating": round(random.uniform(4.0, 5.0), 1),
            f"Avg Consultation Price ({template['currency']})": int(random.uniform(100, 500) * template["price_mult"])
        })
    return pd.DataFrame(data)

# Generate and save
for country in countries:
    print(f"Generating data for {country}...")
    c_dir = BASE_DIR / country
    
    if country != "egypt":
        generate_hotels(country).to_csv(c_dir / "hotels.csv", index=False)
        generate_attractions(country).to_csv(c_dir / "attractions.csv", index=False)
        generate_restaurants(country).to_csv(c_dir / "restaurants.csv", index=False)
        generate_transport(country).to_csv(c_dir / "transport.csv", index=False)
        generate_flights(country).to_csv(c_dir / "flights.csv", index=False)
    
    # Medical centers for all
    generate_medical_centers(country).to_csv(c_dir / "medical_centers.csv", index=False)

print("Synthetic data generation complete!")
