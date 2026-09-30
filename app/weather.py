import re

WEATHER_TERMS = re.compile(
    r"(?:\bweather\b|\bclimate\b|\btemp\b|\btemperature\b|\btemperatures\b|\bhottest\b|\bcoldest\b|"
    r"\b(?:daily )?high\b|\b(?:overnight )?low\b|\bdegrees?\b|°\s*[fc]\b|\bfahrenheit\b|\bcelsius\b|"
    r"\brain(?:fall)?\b|\bprecipitation\b|\bsnow(?:fall)?\b|\bhail\b|\bsleet\b|\bblizzard\b|"
    r"\bhurricanes?\b|\btropical (?:storm|depression)\b|\bnamed storm\b|\blandfall\b|\btornado(?:es)?\b|"
    r"\bstorms?\b|\bwind(?: speed| gust)?\b|\bheat(?: wave| index)?\b|\bfreeze\b|\bfrost\b|"
    r"\bdrought\b|\bair quality\b|\b(?:hdd|cdd)\b|\bheating degree days?\b|\bcooling degree days?\b)", re.I)

# Hydrology and ocean-atmosphere measures are also meteorological/climate
# contracts even when their titles do not literally say "weather".
WEATHER_TERMS = re.compile(
    WEATHER_TERMS.pattern[:-1]
    + r"|\b(?:el ni(?:ñ|n)o|la ni(?:ñ|n)a|roni)\b|\barctic sea ice\b|"
      r"\b(?:river|lake|reservoir)\b.{0,50}\b(?:levels?|elevation)\b)",
    re.I,
)

FALSE_POSITIVES = re.compile(r"\b(miami heat|oklahoma city thunder|carolina hurricanes?|snow crabs?)\b", re.I)

TYPE_PATTERNS = (
    ("Temperature", re.compile(r"\btemp\b|temperature|hottest|coldest|\bdaily high\b|\bovernight low\b|degrees?|°\s*[fc]|fahrenheit|celsius|heat index|\b(?:hdd|cdd)\b|degree days?", re.I)),
    ("Rain & precipitation", re.compile(r"rain(?:fall)?|precipitation|sleet|hail", re.I)),
    ("Snow & freezing", re.compile(r"snow(?:fall)?|blizzard|freeze|frost", re.I)),
    ("Tropical weather", re.compile(r"hurricanes?|tropical (?:storm|depression)|named storm|landfall", re.I)),
    ("Severe storms", re.compile(r"tornado(?:es)?|storms?|wind(?: speed| gust)?", re.I)),
    ("Climate & environment", re.compile(r"climate|drought|air quality", re.I)),
    ("Climate & environment", re.compile(r"el ni(?:ñ|n)o|la ni(?:ñ|n)a|\broni\b|arctic sea ice|(?:river|lake|reservoir).{0,50}(?:levels?|elevation)", re.I)),
)

def metadata_text(*objects):
    values=[]
    for obj in objects:
        if isinstance(obj, dict):
            for key in ("title","question","subtitle","yes_sub_title","no_sub_title","description","rules_primary","rules_secondary","category","ticker","series_ticker"):
                if obj.get(key): values.append(str(obj[key]))
            for tag in obj.get("tags") or []:
                values.append(str(tag.get("label") if isinstance(tag,dict) else tag))
        elif obj: values.append(str(obj))
    return " ".join(values)

def classify_weather(*objects):
    text=metadata_text(*objects)
    if not WEATHER_TERMS.search(text) or FALSE_POSITIVES.search(text):
        return None
    for label,pattern in TYPE_PATTERNS:
        if pattern.search(text): return label
    return "Other weather"

def official_weather_source(weather_type):
    if weather_type in {"Tropical weather","Severe storms"}:
        return "National Weather Service alerts", "https://api.weather.gov/alerts/active"
    if weather_type=="Climate & environment":
        return "NOAA climate data", "https://www.ncei.noaa.gov/cdo-web/"
    return "National Weather Service observations", "https://www.weather.gov/wrh/Climate"
