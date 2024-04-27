from jobs.models import Technology, TechnologyMapping
from utils.constants import HIRABLE_TECH_LIST_MAPPING

for pair in HIRABLE_TECH_LIST_MAPPING:
    print(pair)

    parent = Technology.objects.get(id=pair[0])
    child = Technology.objects.get(id=pair[1])

    TechnologyMapping.objects.get_or_create(parent=parent, child=child)
