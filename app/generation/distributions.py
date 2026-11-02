"""Statistical distributions for persona generation."""

GENDER = [
    ("male", 0.49),
    ("female", 0.49),
    ("non-binary", 0.02),
]

AGE_BRACKETS = [
    ("18-24", 0.15),
    ("25-34", 0.22),
    ("35-44", 0.20),
    ("45-54", 0.18),
    ("55-64", 0.15),
    ("65+", 0.10),
]

EDUCATION = [
    ("high_school", 0.25),
    ("some_college", 0.15),
    ("bachelors", 0.35),
    ("masters", 0.18),
    ("doctorate", 0.07),
]

INCOME_BAND = [
    ("low", 0.20),
    ("lower-middle", 0.25),
    ("middle", 0.30),
    ("upper-middle", 0.18),
    ("high", 0.07),
]

MARITAL_STATUS = [
    ("single", 0.35),
    ("married", 0.45),
    ("divorced", 0.12),
    ("widowed", 0.05),
    ("partnered", 0.03),
]

LOCATION = [
    ("New York, USA", 0.08),
    ("London, UK", 0.07),
    ("Tokyo, Japan", 0.07),
    ("Mumbai, India", 0.08),
    ("São Paulo, Brazil", 0.06),
    ("Berlin, Germany", 0.06),
    ("Toronto, Canada", 0.06),
    ("Sydney, Australia", 0.06),
    ("Singapore", 0.05),
    ("Dubai, UAE", 0.05),
    ("Mexico City, Mexico", 0.07),
    ("Seoul, South Korea", 0.06),
    ("Paris, France", 0.06),
    ("Lagos, Nigeria", 0.08),
    ("Shanghai, China", 0.09),
]

# Occupations grouped by industry with (occupation, industry, base_income_level, min_education)
# base_income_level: 0=low, 1=lower-middle, 2=middle, 3=upper-middle, 4=high
# min_education: minimum education level required (None means any education is acceptable)
OCCUPATIONS = [
    # Technology
    ("software_engineer", "technology", 3, "bachelors"),
    ("data_scientist", "technology", 3, "bachelors"),
    ("it_support", "technology", 2, "some_college"),
    ("product_manager", "technology", 3, "bachelors"),
    
    # Healthcare
    ("nurse", "healthcare", 2, "some_college"),
    ("doctor", "healthcare", 4, "doctorate"),
    ("medical_assistant", "healthcare", 1, "high_school"),
    
    # Education
    ("teacher", "education", 2, "bachelors"),
    ("professor", "education", 3, "doctorate"),
    
    # Business/Finance
    ("accountant", "finance", 2, "bachelors"),
    ("financial_analyst", "finance", 3, "bachelors"),
    ("business_consultant", "business", 3, "bachelors"),
    ("marketing_manager", "business", 3, "bachelors"),
    
    # Retail/Service
    ("retail_worker", "retail", 1, None),
    ("restaurant_server", "hospitality", 1, None),
    ("customer_service_rep", "service", 1, None),
    
    # Trade/Manufacturing
    ("electrician", "trade", 2, "high_school"),
    ("mechanic", "trade", 2, "high_school"),
    ("factory_worker", "manufacturing", 1, None),
    
    # Other
    ("driver", "transportation", 1, None),
    ("small_business_owner", "business", 2, None),
    ("farmer", "agriculture", 1, None),
    ("freelancer", "creative", 2, None),
    ("student", "education", 0, None),
    ("retired", "none", 1, None),
]

# Education level ordering for comparison
EDUCATION_LEVELS = {
    "high_school": 0,
    "some_college": 1,
    "bachelors": 2,
    "masters": 3,
    "doctorate": 4,
}

SHOPPING_HABITS = [
    ("online_primary", 0.35),
    ("in_store_primary", 0.25),
    ("balanced", 0.30),
    ("impulse_buyer", 0.10),
]

BRAND_LOYALTY = [
    ("high", 0.25),
    ("medium", 0.45),
    ("low", 0.30),
]

SPENDING_STYLE = [
    ("frugal", 0.30),
    ("moderate", 0.45),
    ("generous", 0.20),
    ("luxury", 0.05),
]

PREFERRED_DEVICES = [
    "smartphone",
    "laptop",
    "desktop",
    "tablet",
    "smartwatch",
    "smart_tv",
]
