import os
from pathlib import Path

BASE_DIR = Path("/Users/abdelruhamanelfekky/Desktop/Gen project/Touri/BackEnd/data/travel_guides")

guides = {
    "saudi_arabia": {
        "riyadh_guide.md": "# Riyadh Travel Guide\n\nRiyadh, Saudi Arabia's capital and main financial hub, is on a desert plateau in the country's center.\n\n## Top Attractions\n- National Museum\n- Kingdom Centre Tower\n- Al Masmak Fortress",
        "jeddah_guide.md": "# Jeddah Travel Guide\n\nJeddah, a Saudi Arabian port city on the Red Sea, is a modern commercial hub and gateway for pilgrimages to the Islamic holy cities Mecca and Medina.\n\n## Top Attractions\n- Al-Balad\n- King Fahd's Fountain\n- Red Sea Mall",
        "medical_tourism_saudi.md": "# Medical Tourism in Saudi Arabia\n\nSaudi Arabia offers world-class medical facilities, particularly in Riyadh and Jeddah. It is known for its advanced specialized hospitals and wellness resorts.\n\n## Top Specialties\n- Cardiovascular Surgery\n- Oncology\n- Wellness and Rehabilitation"
    },
    "qatar": {
        "doha_guide.md": "# Doha Travel Guide\n\nDoha is the capital city and main financial hub of Qatar. Located on the Persian Gulf coast, it is known for its modern architecture and cultural heritage.\n\n## Top Attractions\n- Museum of Islamic Art\n- Souq Waqif\n- The Pearl-Qatar",
        "medical_tourism_qatar.md": "# Medical Tourism in Qatar\n\nQatar is rapidly developing its medical tourism sector with state-of-the-art hospitals like Sidra Medicine and Aspetar.\n\n## Top Specialties\n- Sports Medicine\n- Women's and Children's Health\n- Luxury Wellness"
    },
    "turkey": {
        "istanbul_guide.md": "# Istanbul Travel Guide\n\nIstanbul is a major city in Turkey that straddles Europe and Asia across the Bosphorus Strait. Its Old City reflects cultural influences of the many empires that once ruled here.\n\n## Top Attractions\n- Hagia Sophia\n- Topkapi Palace\n- Grand Bazaar",
        "antalya_guide.md": "# Antalya Travel Guide\n\nAntalya is a Turkish resort city with a yacht-filled Old Harbor and beaches flanked by large hotels. It's a gateway to Turkey's southern Mediterranean region.\n\n## Top Attractions\n- Hadrian's Gate\n- Duden Waterfalls\n- Antalya Museum",
        "medical_tourism_turkey.md": "# Medical Tourism in Turkey\n\nTurkey is a global hub for medical tourism, particularly famous for hair transplants, cosmetic surgery, and dental procedures.\n\n## Top Specialties\n- Hair Transplants\n- Cosmetic Surgery\n- Dentistry\n- Orthopedics"
    },
    "morocco": {
        "marrakech_guide.md": "# Marrakech Travel Guide\n\nMarrakech, a former imperial city in western Morocco, is a major economic center and home to mosques, palaces and gardens.\n\n## Top Attractions\n- Jardin Majorelle\n- Bahia Palace\n- Jemaa el-Fnaa",
        "casablanca_guide.md": "# Casablanca Travel Guide\n\nCasablanca is a port city and commercial hub in western Morocco, fronting the Atlantic Ocean. The city's French colonial legacy is seen in its downtown Mauresque architecture.\n\n## Top Attractions\n- Hassan II Mosque\n- Morocco Mall\n- Old Medina",
        "medical_tourism_morocco.md": "# Medical Tourism in Morocco\n\nMorocco combines medical treatments with wellness and recovery in a relaxing environment, often incorporating traditional Hammam practices.\n\n## Top Specialties\n- Cosmetic Surgery\n- Wellness Retreats\n- Dental Care"
    },
    "egypt": {
        "medical_tourism_egypt.md": "# Medical Tourism in Egypt\n\nEgypt is a popular destination for medical tourism, offering affordable and high-quality treatments, especially in Cairo and Alexandria.\n\n## Top Specialties\n- Dental Care\n- Lasik and Eye Care\n- Cosmetic Procedures\n- Orthopedics"
    }
}

for country, files in guides.items():
    c_dir = BASE_DIR / country
    c_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        with open(c_dir / filename, "w") as f:
            f.write(content)

print("Travel guides generation complete!")
