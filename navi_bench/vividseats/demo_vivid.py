#!/usr/bin/env python
import asyncio
import sys
from dataclasses import dataclass, field
from playwright.async_api import async_playwright
from loguru import logger

# Import your new Vivid Seats evaluator
from vivid_info_gathering import VividSeatsInfoGathering

@dataclass
class BrowserConfig:
    headless: bool = False
    viewport_width: int = 1366
    viewport_height: int = 768
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    locale: str = "en-US"
    launch_args: list = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-sandbox",
    ])

@dataclass
class TaskScenario:
    task_id: str
    name: str
    description: str
    url: str
    task_prompt: str
    queries: list
    location: str = "United States"
    timezone: str = "America/New_York"
    category: str = "unknown"
    tags: list = field(default_factory=list)

SCENARIOS: list[TaskScenario] = [
    TaskScenario(
        task_id="vividseats/concerts/bruno_mars/las_vegas",
        name="Bruno Mars - Las Vegas General",
        description="Search for Bruno Mars tickets in Las Vegas.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for Bruno Mars concert tickets in Las Vegas and check general availability."
        ),
        queries=[[{
            "event_names": ["bruno mars"], 
            "cities": ["las vegas"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="concerts",
        tags=["music", "pop", "bruno_mars"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/bruno_mars/glendale_budget",
        name="Bruno Mars - Glendale Under $200",
        description="Find Bruno Mars tickets in Glendale priced under $200.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find me tickets to see Bruno Mars in Glendale, AZ."
        ),
        queries=[[{
            "event_names": ["bruno mars"], 
            "cities": ["glendale"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Phoenix",
        category="concerts",
        tags=["music", "budget", "arizona"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/bruno_mars/texas_options",
        name="Bruno Mars - Texas Shows",
        description="Search for Bruno Mars tickets in Texas (Arlington or Houston).",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I want to see Bruno Mars in Texas. Check the availability for shows in either Arlington or Houston."
        ),
        queries=[[{
            "event_names": ["bruno mars"], 
            "cities": ["arlington", "houston"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Chicago",
        category="concerts",
        tags=["music", "texas", "multi_city"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/bruno_mars/atlanta_deal",
        name="Bruno Mars - Atlanta Deal",
        description="Find a reasonably priced ticket for Bruno Mars in Atlanta.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for Bruno Mars in Atlanta, GA. Tickets should be priced below $210."
        ),
        queries=[[{
            "event_names": ["bruno mars"], 
            "cities": ["atlanta"],
            "max_price": 210.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="concerts",
        tags=["music", "atlanta", "budget"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/bruno_mars/charlotte_standard",
        name="Bruno Mars - Charlotte Availability",
        description="Check if Bruno Mars is playing in Charlotte and confirm availability.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Can you check Vivid Seats to see if there are any tickets available for Bruno Mars in Charlotte, NC?"
        ),
        queries=[[{
            "event_names": ["bruno mars"], 
            "cities": ["charlotte"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="concerts",
        tags=["music", "charlotte"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/bts/el_paso_general",
        name="BTS - El Paso Availability",
        description="Search for BTS concert tickets in El Paso.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for BTS (Bangtan Boys) concert tickets in El Paso, TX and check if there is any general availability."
        ),
        queries=[[{
            "event_names": ["bts"], 
            "cities": ["el paso"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Denver", # El Paso is Mountain Time
        category="concerts",
        tags=["music", "kpop", "bts"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/bts/el_paso_strict_budget",
        name="BTS - El Paso Under $190",
        description="Find BTS tickets in El Paso for under $190.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find me tickets to see BTS at Sun Bowl Stadium in El Paso, find me options priced under $190."
        ),
        queries=[[{
            "event_names": ["bts"], 
            "cities": ["el paso"],
            "max_price": 190.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Denver",
        category="concerts",
        tags=["music", "budget", "bts"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/bts/super_seller_only",
        name="BTS - Super Seller Guarantee",
        description="Search for BTS tickets sold only by Super Sellers.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for BTS tickets in El Paso, please ensure to find a 'Super Seller' ticket."
        ),
        queries=[[{
            "event_names": ["bts"], 
            "cities": ["el paso"],
            "require_super_seller": True,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Denver",
        category="concerts",
        tags=["music", "kpop", "super_seller"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/bts/bowl_1_specific",
        name="BTS - Section Bowl 1",
        description="Find tickets specifically in Section Bowl 1.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check the Vivid Seats listings for BTS in El Paso. Check specifically for tickets in Section Bowl 1."
        ),
        queries=[[{
            "event_names": ["bts"], 
            "sections": ["bowl 1"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Denver",
        category="concerts",
        tags=["music", "specific_section", "bts"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/bts/bowl_12_super_seller",
        name="BTS - Bowl 12 Super Seller",
        description="Find a Super Seller ticket in Bowl 12.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find Bowl 12 for the BTS concert in El Paso, but it must be sold by a Super Seller."
        ),
        queries=[[{
            "event_names": ["bts"], 
            "sections": ["bowl 12"],
            "require_super_seller": True, 
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Denver",
        category="concerts",
        tags=["music", "kpop", "niche_query"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/bts/bowl_19_check",
        name="BTS - Bowl 19 Availability",
        description="Check if Bowl 19 has available tickets.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "My friends are sitting in Bowl 19 for the BTS concert in El Paso. Check if there are any tickets left in that section."
        ),
        queries=[[{
            "event_names": ["bts"], 
            "sections": ["bowl 19"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Denver",
        category="concerts",
        tags=["music", "seat_matching"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/bts/bowl_26_general",
        name="BTS - Bowl 26 Price Check",
        description="Verify the price for tickets in Bowl 26.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check the Vivid Seats listing for BTS in El Paso to know if I can get a ticket in Bowl 26 for under $215."
        ),
        queries=[[{
            "event_names": ["bts"], 
            "sections": ["bowl 26"], 
            "max_price": 215.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Denver",
        category="concerts",
        tags=["music", "price_verification"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/the_weeknd/munich_general",
        name="The Weeknd - Munich Availability",
        description="Search for The Weeknd tickets in Munich.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for The Weeknd concert tickets in Munich, Germany and check if there is general availability."
        ),
        queries=[[{
            "event_names": ["the weeknd"], 
            "cities": ["munich"],
            "require_available": True,
        }]],
        location="United States",
        timezone="Europe/Berlin",
        category="concerts",
        tags=["music", "pop", "international", "the_weeknd"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/the_weeknd/zone_300_level",
        name="The Weeknd - 300 Level Zone Filter",
        description="Verify the agent can apply the '300 Level' zone filter.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find tickets for The Weeknd in Munich only in the '300 Level' zone area."
        ),
        queries=[[{
            "event_names": ["the weeknd"], 
            "cities": ["munich"],
            "zones": ["300 level"],
            "require_available": True,
        }]],
        location="United States",
        timezone="Europe/Berlin",
        category="concerts",
        tags=["music", "zone_filter", "the_weeknd"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/the_weeknd/munich_budget_check",
        name="The Weeknd - Munich Under $200",
        description="Find budget tickets for The Weeknd in Munich.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find me tickets to see The Weeknd at Allianz Arena in Munich. My maximum budget is $200 per ticket."
        ),
        queries=[[{
            "event_names": ["the weeknd"], 
            "cities": ["munich"],
            "max_price": 200.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="Europe/Berlin",
        category="concerts",
        tags=["music", "budget_check", "europe"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/the_weeknd/section_327_specific",
        name="The Weeknd - Section 327",
        description="Find tickets specifically in Section 327.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check the Vivid Seats listings for The Weeknd in Munich. Look out for tickets psecifically in Section 327."
        ),
        queries=[[{
            "event_names": ["the weeknd"], 
            "sections": ["section 327"], # Matches the $185 ticket
            "require_available": True,
        }]],
        location="United States",
        timezone="Europe/Berlin",
        category="concerts",
        tags=["music", "specific_section"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/the_weeknd/allianz_arena_search",
        name="The Weeknd - Allianz Arena",
        description="Search for shows specifically at the Allianz Arena.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for tickets to see The Weeknd performing at the Allianz Arena."
        ),
        queries=[[{
            "event_names": ["the weeknd"], 
            "venues": ["allianz arena"], # Matches the venue name directly
            "require_available": True,
        }]],
        location="United States",
        timezone="Europe/Berlin",
        category="concerts",
        tags=["music", "venue_search"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/the_weeknd/zone_budget_combo",
        name="The Weeknd - 300 Level Under $250",
        description="Combine a Zone filter with a strict budget constraint.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Look for The Weeknd tickets in Munich. Ensure the tickets cost less than $250 and are in the 300 Level zone."
        ),
        queries=[[{
            "event_names": ["the weeknd"], 
            "zones": ["300 level"], 
            "max_price": 250.0, 
            "require_available": True,
        }]],
        location="United States",
        timezone="Europe/Berlin",
        category="concerts",
        tags=["music", "zone_filter", "budget"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/the_weeknd/multi_section_choice",
        name="The Weeknd - Section 310 or 320",
        description="Search for tickets in one of two specific sections.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "For The Weeknd's show in Munich, check if tickets are available in either Section 310 or Section 320."
        ),
        queries=[[{
            "event_names": ["the weeknd"], 
            "sections": ["section 310", "section 320"],
            "require_available": True,
        }]],
        location="United States",
        timezone="Europe/Berlin",
        category="concerts",
        tags=["music", "multi_section", "premium_pricing"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/the_weeknd/specific_row_check",
        name="The Weeknd - Section 317 Row 12",
        description="Verify a ticket exists in an exact section and row.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Look for tickets in Section 317, Row 12 for The Weeknd in Munich. Check if there is anything available."
        ),
        queries=[[{
            "event_names": ["the weeknd"], 
            "sections": ["section 317"],
            "rows": ["12"],
            "require_available": True,
        }]],
        location="United States",
        timezone="Europe/Berlin",
        category="concerts",
        tags=["music", "exact_seat_search"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/the_weeknd/premium_budget_check",
        name="The Weeknd - Premium Seats Under $800",
        description="Find premium location tickets under $800.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Look in Section 306 or Section 311, and make sure the ticket is under $800."
        ),
        queries=[[{
            "event_names": ["the weeknd"], 
            "sections": ["section 306", "section 311"],
            "max_price": 800.0, # Matches the $798 tickets
            "require_available": True,
        }]],
        location="United States",
        timezone="Europe/Berlin",
        category="concerts",
        tags=["music", "high_budget", "multi_section"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/the_weeknd/mid_tier_pricing",
        name="The Weeknd - Mid-Tier Price Evaluation",
        description="Find tickets in Section 308, 309, or 322 priced under $775.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check the availability for tickets of The Weeknd concert in Munich in Sections 308, 309, or 322. I want to spend less than $775."
        ),
        queries=[[{
            "event_names": ["the weeknd"], 
            "sections": ["section 308", "section 309", "section 322"],
            "max_price": 775.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="Europe/Berlin",
        category="concerts",
        tags=["music", "price_verification"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lady_gaga/ny_group_budget",
        name="Lady Gaga - NY Group Under $800",
        description="Find tickets for a group of 6 in New York under $800.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find tickets for Lady Gaga in New York, NY for a group of 6 people. The budget is between $700 to $800 per ticket."
        ),
        queries=[[{
            "event_names": ["lady gaga"], 
            "cities": ["new york"],
            "quantity": 6,
            "min_price": 700.0,
            "max_price": 800.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="concerts",
        tags=["music", "pop", "lady_gaga", "budget"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lady_gaga/msg_section_115",
        name="Lady Gaga - Section 115",
        description="Verify availability for a group of 6 in Section 115.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for Lady Gaga at Madison Square Garden. Set the ticket quantity to 6 and check if there are any tickets available in Section 115."
        ),
        queries=[[{
            "event_names": ["lady gaga"], 
            "venues": ["madison square garden"],
            "quantity": 6,
            "sections": ["section 115"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="concerts",
        tags=["music", "specific_section"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lady_gaga/msg_row_12",
        name="Lady Gaga - Section 115 Row 12",
        description="Check for tickets specifically in Row 12 of Section 115.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I need exactly 6 tickets for Lady Gaga in New York. Can you see if Section 115, Row 12 is available?"
        ),
        queries=[[{
            "event_names": ["lady gaga"], 
            "cities": ["new york"],
            "quantity": 6,
            "sections": ["section 115"],
            "rows": ["12"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="concerts",
        tags=["music", "exact_seat_search"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lady_gaga/msg_super_seller",
        name="Lady Gaga - MSG Super Seller Only",
        description="Find 6 tickets at MSG sold by a Super Seller.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for 6 tickets to Lady Gaga at Madison Square Garden. Ensure it is a 'Super Seller' category ticket."
        ),
        queries=[[{
            "event_names": ["lady gaga"], 
            "venues": ["madison square garden"],
            "quantity": 6,
            "require_super_seller": True, # Matches the $1477 ticket in Section 224
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="concerts",
        tags=["music", "super_seller", "msg"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lady_gaga/mid_tier_budget",
        name="Lady Gaga - NYC Under $1300",
        description="Find 6 Lady Gaga tickets priced under $1300.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find a group of 6 tickets for Lady Gaga in New York. Show me options that cost less than $1300 per ticket."
        ),
        queries=[[{
            "event_names": ["lady gaga"], 
            "cities": ["new york"],
            "quantity": 6,
            "max_price": 1300.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="concerts",
        tags=["music", "budget_check"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lady_gaga/multi_section_search",
        name="Lady Gaga - Section 109 or 120",
        description="Check availability for 6 tickets in one of two specific sections.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "For the Lady Gaga show in NYC, check if there are 6 tickets available in either Section 109 or Section 120."
        ),
        queries=[[{
            "event_names": ["lady gaga"], 
            "cities": ["new york"],
            "sections": ["section 109", "section 120"],
            "quantity": 6,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="concerts",
        tags=["music", "multi_section", "premium"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lady_gaga/front_rows_high_budget",
        name="Lady Gaga - Rows 5 or 6",
        description="Find tickets in Row 5 or 6 with a high budget limit.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find 6 tickets in either Row 5 or Row 6 for Lady Gaga's show in New York, they should be priced under $2000 each."
        ),
        queries=[[{
            "event_names": ["lady gaga"], 
            "cities": ["new york"],
            "rows": ["5", "6"], # Matches Sec 109 (Row 6) and Sec 119 (Row 5)
            "quantity": 6,
            "max_price": 2000.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="concerts",
        tags=["music", "premium_seating", "close_rows"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lady_gaga/section_200s_block",
        name="Lady Gaga - 200 Level Options",
        description="Find 6 tickets in the 200-level sections.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find 6 tickets for Lady Gaga in New York somewhere in the 200-level sections, specifically checking Section 211 or Section 224."
        ),
        queries=[[{
            "event_names": ["lady gaga"], 
            "cities": ["new york"],
            "sections": ["section 211", "section 224"],
            "quantity": 6,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="concerts",
        tags=["music", "upper_level", "specific_section"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lady_gaga/section_104_exact",
        name="Lady Gaga - Section 104 Validation",
        description="Verify a ticket exists exactly in Section 104.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check the Vivid Seats listing for Lady Gaga at MSG. I want to know if I can get 6 tickets in Section 104."
        ),
        queries=[[{
            "event_names": ["lady gaga"], 
            "venues": ["madison square garden"],
            "sections": ["section 104"],
            "quantity": 6,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="concerts",
        tags=["music", "exact_seat_search", "msg"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lewis_capaldi/la_group",
        name="Lewis Capaldi - LA General Group",
        description="Search for a group of 3 tickets for Lewis Capaldi in Los Angeles.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for Lewis Capaldi concert tickets in Los Angeles. I need exactly 3 tickets."
        ),
        queries=[[{
            "event_names": ["lewis capaldi"], 
            "cities": ["los angeles"],
            "quantity": 3,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="concerts",
        tags=["music", "pop", "lewis_capaldi", "group_tickets"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lewis_capaldi/zone_filter_promenade",
        name="Lewis Capaldi - Promenade Zones",
        description="Verify the agent can apply the Promenade 1 or Promenade 2 zone filters.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find 3 tickets for Lewis Capaldi in Los Angeles. Strictly look at 'Promenade 1' or 'Promenade 2' seats."
        ),
        queries=[[{
            "event_names": ["lewis capaldi"], 
            "zones": ["promenade 1", "promenade 2"],
            "quantity": 3,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="concerts",
        tags=["music", "zone_filter", "promenade"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lewis_capaldi/strict_budget_110",
        name="Lewis Capaldi - Under $110",
        description="Find 3 tickets at the Hollywood Bowl under $110 each.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Look for 3 tickets to the Lewis Capaldi show at the Hollywood Bowl. The tickets should be priced below $110 per ticket."
        ),
        queries=[[{
            "event_names": ["lewis capaldi"], 
            "venues": ["hollywood bowl"],
            "quantity": 3,
            "max_price": 110.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="concerts",
        tags=["music", "budget_check", "hollywood_bowl"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lewis_capaldi/super_seller_f2_k2",
        name="Lewis Capaldi - Safe Purchase F2/K2",
        description="Find Super Seller tickets in either Promenade F2 or K2.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I want to sit in either Promenade F2 or Promenade K2 for Lewis Capaldi. Find me 3 tickets, and make sure they are listed by a 'Super Seller'."
        ),
        queries=[[{
            "event_names": ["lewis capaldi"], 
            "sections": ["promenade f2", "promenade k2"],
            "quantity": 3,
            "require_super_seller": True,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="concerts",
        tags=["music", "super_seller", "multi_section"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lewis_capaldi/row_19_exact",
        name="Lewis Capaldi - Row 19 Availability",
        description="Verify availability of 3 tickets in Row 19.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check the Vivid Seats listings for Lewis Capaldi in Los Angeles. I specifically want 3 tickets in Row 19."
        ),
        queries=[[{
            "event_names": ["lewis capaldi"], 
            "rows": ["19"], 
            "quantity": 3,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="concerts",
        tags=["music", "row_search"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lewis_capaldi/zone_plus_budget",
        name="Lewis Capaldi - Zone Filter + $150 Budget",
        description="Combine Zone filter logic with a budget constraint.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for 3 tickets to Lewis Capaldi. Apply the 'Promenade 1' zone filter and ensure that the tickets are priced under $150."
        ),
        queries=[[{
            "event_names": ["lewis capaldi"], 
            "zones": ["promenade 1"],
            "max_price": 150.0,
            "quantity": 3,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="concerts",
        tags=["music", "zone_filter", "budget"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lewis_capaldi/f3_section_check",
        name="Lewis Capaldi - Section F3 Validation",
        description="Find 3 tickets exactly in Promenade F3.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check if there are 3 tickets available in Promenade F3 for the Lewis Capaldi show in LA."
        ),
        queries=[[{
            "event_names": ["lewis capaldi"], 
            "sections": ["promenade f3"],
            "quantity": 3,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="concerts",
        tags=["music", "exact_seat_search"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lewis_capaldi/super_seller_row_21",
        name="Lewis Capaldi - Super Seller Row 21",
        description="Find a Super Seller ticket specifically in Row 21.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I need 3 tickets in Row 21 for Lewis Capaldi in Los Angeles, but I will only buy them if they are from a Super Seller. Check for any such availablity."
        ),
        queries=[[{
            "event_names": ["lewis capaldi"], 
            "rows": ["21"], 
            "quantity": 3,
            "require_super_seller": True,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="concerts",
        tags=["music", "niche_query", "super_seller"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lewis_capaldi/mid_tier_budget_check",
        name="Lewis Capaldi - Any Seat Under $115",
        description="Verify the agent can capture tickets in the $111 range.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find a group of 3 tickets for Lewis Capaldi at the Hollywood Bowl. Show me options that cost less than $115 per ticket."
        ),
        queries=[[{
            "event_names": ["lewis capaldi"], 
            "venues": ["hollywood bowl"],
            "quantity": 3,
            "max_price": 115.0, # Captures all standard tickets listed at $111
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="concerts",
        tags=["music", "budget_check"],
    ),
    TaskScenario(
        task_id="vividseats/concerts/lewis_capaldi/f1_or_k1_standard",
        name="Lewis Capaldi - K1 or F1 Sections",
        description="Search for tickets in Promenade K1 or F1.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I want to compare prices for 3 tickets in either Promenade F1 or Promenade K1 for Lewis Capaldi in Los Angeles."
        ),
        queries=[[{
            "event_names": ["lewis capaldi"], 
            "sections": ["promenade f1", "promenade k1"],
            "quantity": 3,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="concerts",
        tags=["music", "multi_section", "comparison"],
    ),
    TaskScenario(
        task_id="vividseats/sports/lakers/bulls_home",
        name="Lakers vs Bulls - LA Check",
        description="Find tickets for the Lakers home game against the Chicago Bulls.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for tickets to the Los Angeles Lakers vs Chicago Bulls game in LA on March 12, 2026."
        ),
        queries=[[{
            "event_names": ["lakers", "bulls"], 
            "cities": ["los angeles"],
            "dates": ["2026-03-12"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="sports",
        tags=["sports", "nba", "lakers", "home_game"],
    ),
    TaskScenario(
        task_id="vividseats/sports/lakers/miami_away",
        name="Lakers vs Heat - Miami Away Game",
        description="Find an away game for the Lakers in Miami.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I want to see the Lakers play on the road against the Miami Heat on March 19, 2026. Check if there are tickets available."
        ),
        queries=[[{
            "event_names": ["lakers", "heat"], 
            "cities": ["miami"],
            "dates": ["2026-03-19"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="sports",
        tags=["sports", "nba", "lakers", "away_game"],
    ),
    TaskScenario(
        task_id="vividseats/sports/lakers/houston_multi_date",
        name="Lakers vs Rockets - Houston Series",
        description="Check availability for either of the Lakers away games in Houston.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "The Lakers are playing two games in Houston in mid-March 2026. Find available tickets for either the March 16 or March 18 game."
        ),
        queries=[[{
            "event_names": ["lakers", "rockets"], 
            "cities": ["houston"],
            "dates": ["2026-03-16", "2026-03-18"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Chicago",
        category="sports",
        tags=["sports", "nba", "lakers", "multi_date", "away_game"],
    ),
    TaskScenario(
        task_id="vividseats/sports/knicks/100_level_zones",
        name="Knicks vs Raptors - 100 Level Zones",
        description="Filter for 100 Level zones to find 2 tickets.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for 2 tickets to the Knicks vs Raptors game. Specifically look at '100 Level - Baseline' or '100 Level - Sideline' zones."
        ),
        queries=[[{
            "event_names": ["knicks", "raptors"],
            "quantity": 2,
            "zones": ["100 level - baseline", "100 level - sideline"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="sports",
        tags=["sports", "nba", "knicks", "zone_filter"],
    ),
    TaskScenario(
        task_id="vividseats/sports/knicks/sec_112_super_seller",
        name="Knicks vs Raptors - Sec 112 Super Seller",
        description="Find 2 Super Seller tickets specifically in Section 112.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I want 2 tickets in Section 112 for the Knicks vs Raptors game, but they must be from a Super Seller."
        ),
        queries=[[{
            "event_names": ["knicks", "raptors"],
            "sections": ["section 112"],
            "quantity": 2,
            "require_super_seller": True, # Matches the $234 ticket exactly
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="sports",
        tags=["sports", "nba", "super_seller", "specific_section"],
    ),
    TaskScenario(
        task_id="vividseats/sports/knicks/rows_21_22_budget",
        name="Knicks vs Raptors - Rows 21/22 Budget",
        description="Check for 2 tickets in Row 21 or 22 under $250.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check the Vivid Seats listings for the Knicks game. I want 2 tickets in either Row 21 or Row 22 that cost less than $250."
        ),
        queries=[[{
            "event_names": ["knicks"],
            "rows": ["21", "22"],
            "max_price": 250.0,
            "quantity": 2,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="sports",
        tags=["sports", "row_search", "budget"],
    ),
    TaskScenario(
        task_id="vividseats/sports/knicks/sec_101_102_comparison",
        name="Knicks vs Raptors - Sections 101 or 102",
        description="Find 2 tickets in Section 101 or 102.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find me 2 tickets in either Section 101 or Section 102 for the upcoming Knicks game against the Raptors. "
        ),
        queries=[[{
            "event_names": ["knicks"],
            "sections": ["section 101", "section 102"],
            "quantity": 2,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="sports",
        tags=["sports", "multi_section"],
    ),
    TaskScenario(
        task_id="vividseats/sports/knicks/sec_111_row_18",
        name="Knicks vs Raptors - Exact Seat Verification",
        description="Verify if 2 tickets are available in Section 111, Row 18.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Verify if there are exactly 2 tickets available in Section 111, Row 18 for the Knicks vs Raptors game at MSG."
        ),
        queries=[[{
            "event_names": ["knicks", "raptors"],
            "venues": ["madison square garden"],
            "sections": ["section 111"],
            "rows": ["18"],
            "quantity": 2,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="sports",
        tags=["sports", "exact_seat_search"],
    ),
    TaskScenario(
        task_id="vividseats/sports/knicks/strict_budget_225",
        name="Knicks vs Raptors - Deal Under $225",
        description="Find the cheapest possible pair of tickets under $225.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I need a pair of tickets (2) to the Knicks vs Raptors game, but my budget is below $225 per ticket."
        ),
        queries=[[{
            "event_names": ["knicks", "raptors"],
            "max_price": 225.0,
            "quantity": 2,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="sports",
        tags=["sports", "budget_check"],
    ),
    TaskScenario(
        task_id="vividseats/sports/knicks/west_balcony_zone",
        name="Knicks vs Raptors - West Balcony Filter",
        description="Apply the West Balcony zone filter.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find 2 tickets for the Knicks game in the 'West Balcony' zone."
        ),
        queries=[[{
            "event_names": ["knicks"],
            "zones": ["west balcony"],
            "quantity": 2,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="sports",
        tags=["sports", "zone_filter"],
    ),
    TaskScenario(
        task_id="vividseats/sports/knicks/sec_102_budget",
        name="Knicks vs Raptors - Sec 102 Check",
        description="Find available tickets in Section 102 under $250.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find 2 tickets in Section 102 for the Knicks game that are priced below $250."
        ),
        queries=[[{
            "event_names": ["knicks"],
            "sections": ["section 102"],
            "max_price": 250.0,
            "quantity": 2,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="sports",
        tags=["sports", "specific_section", "budget"],
    ),
    TaskScenario(
        task_id="vividseats/theater/beauty_and_the_beast/late_april",
        name="Beauty And The Beast - Late April Availability",
        description="Check for Beauty and the Beast tickets available in late April.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for Beauty and the Beast tickets between April 21 to April 29 to check for general availability."
        ),
        queries=[[{
            "event_names": ["beauty and the beast"], 
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="theater",
        tags=["theater", "musical", "family", "date_filter"],
    ),
    TaskScenario(
        task_id="vividseats/theater/beauty_and_the_beast/apr_21_budget",
        name="Beauty and the Beast - April 21 Under $80",
        description="Find a ticket for Beauty and the Beast on April 21 under $80.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for tickets to see the Beauty and the Beast musical on April 21, 2026."
        ),
        queries=[[{
            "event_names": ["beauty and the beast"], 
            "dates": ["2026-04-21"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="theater",
        tags=["theater", "budget", "specific_date"],
    ),
    TaskScenario(
        task_id="vividseats/theater/beauty_and_the_beast/apr_25_general",
        name="Beauty and the Beast - April 25 General",
        description="Check general availability for the April 25th show.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check Vivid Seats to see if there are any tickets available for Beauty and the Beast on April 25, 2026."
        ),
        queries=[[{
            "event_names": ["beauty and the beast"], 
            "dates": ["2026-04-25"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="theater",
        tags=["theater", "availability_check", "specific_date"],
    ),
    TaskScenario(
        task_id="vividseats/theater/beauty_and_the_beast/apr_28_deal",
        name="Beauty and the Beast - April 28 Deal",
        description="Find the absolute cheapest ticket on April 28.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I want to catch the Beauty and the Beast show on April 28, 2026."
        ),
        queries=[[{
            "event_names": ["beauty and the beast"], 
            "dates": ["2026-04-28"], 
            "require_available": True,
        }]],
        location="United States",
        timezone="America/New_York",
        category="theater",
        tags=["theater", "deal_hunting", "specific_date"],
    ),
    TaskScenario(
        task_id="vividseats/comedy/gabriel_iglesias/dallas_cheap",
        name="Gabriel Iglesias - Dallas Minimum Price",
        description="Find the cheapest available ticket for Gabriel Iglesias in Dallas.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find a single ticket available for Gabriel Iglesias at the Improv Comedy Club in Dallas on April 17. Ensure the ticket price is at least $120."
        ),
        queries=[[{
            "event_names": ["gabriel iglesias"],
            "cities": ["dallas"],
            "dates": ["2026-04-17"],
            "quantity": 1,
            "min_price": 120.0, # Matches the $127 ticket
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Chicago",
        category="comedy",
        tags=["comedy", "fluffy", "budget"],
    ),
    TaskScenario(
        task_id="vividseats/comedy/gabriel_iglesias/ga_row_4",
        name="Gabriel Iglesias - Row 4 Specific",
        description="Find a ticket specifically in Row 4 of General Admission.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I want to see Gabriel Iglesias in Dallas. Please find me a single ticket specifically in 'Row 4' of the General Admission section."
        ),
        queries=[[{
            "event_names": ["gabriel iglesias"],
            "sections": ["general admission"],
            "rows": ["4"], 
            "quantity": 1,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Chicago",
        category="comedy",
        tags=["comedy", "specific_row"],
    ),
    TaskScenario(
        task_id="vividseats/comedy/gabriel_iglesias/dallas_mid_range",
        name="Gabriel Iglesias - Dallas Mid-Range",
        description="Find a ticket for Gabriel Iglesias between $150 and $180.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for Gabriel Iglesias tickets in Dallas. I'm looking for a mid-range seat, so find me a ticket that costs at least $150 but no more than $180."
        ),
        queries=[[{
            "event_names": ["gabriel iglesias"],
            "quantity": 1,
            "min_price": 150.0,
            "max_price": 180.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Chicago",
        category="comedy",
        tags=["comedy", "price_range"],
    ),
    TaskScenario(
        task_id="vividseats/comedy/gabriel_iglesias/apr_17_general",
        name="Gabriel Iglesias - April 17 Check",
        description="Verify availability for the April 17th show in Dallas.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check Vivid Seats to see if there are any tickets available for Gabriel Iglesias on April 17, 2026, in Dallas."
        ),
        queries=[[{
            "event_names": ["gabriel iglesias"],
            "dates": ["2026-04-17"],
            "quantity": 1,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Chicago",
        category="comedy",
        tags=["comedy", "specific_date"],
    ),
    TaskScenario(
        task_id="vividseats/comedy/gabriel_iglesias/ga_row_check",
        name="Gabriel Iglesias - Row GA or GAO",
        description="Find a ticket in either Row GA or GAO.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Look for tickets to the Gabriel Iglesias show at the Improv Comedy Club. I'm looking for General Admission "
            "tickets in either 'Row GA' or 'Row GAO'."
        ),
        queries=[[{
            "event_names": ["gabriel iglesias"],
            "rows": ["ga", "gao"], # Matches the $183 and $127 tickets
            "quantity": 1,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Chicago",
        category="comedy",
        tags=["comedy", "row_search"],
    ),
    TaskScenario(
        task_id="vividseats/theater/les_miserables/boise_group_budget",
        name="Les Miserables - Boise Large Group",
        description="Find a block of 8 tickets in Boise for under $150.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I need to find 8 tickets together for Les Misérables at the Morrison Center in Boise on April 21, 2026 strictly under $150 per ticket."
        ),
        queries=[[{
            "event_names": ["les miserables"], 
            "cities": ["boise"],
            "dates": ["2026-04-21"],
            "quantity": 8,
            "max_price": 150.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Boise",
        category="theater",
        tags=["theater", "musical", "group_tickets", "budget"],
    ),
    TaskScenario(
        task_id="vividseats/theater/les_miserables/main_floor_super_seller",
        name="Les Miserables - Main Floor Super Seller",
        description="Verify a Super Seller ticket on the Main Floor.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for Les Misérables tickets in Boise. I specifically want to sit on the 'Main Floor' and I only want to buy from a 'Super Seller'. Find me 8 tickets matching this description."
        ),
        queries=[[{
            "event_names": ["les miserables"], 
            "zones": ["main floor"],
            "quantity": 8,
            "require_super_seller": True,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Boise",
        category="theater",
        tags=["theater", "zone_filter", "super_seller"],
    ),
    TaskScenario(
        task_id="vividseats/theater/les_miserables/row_r_or_s_check",
        name="Les Miserables - Row R or S Check",
        description="Find 8 tickets in Row R or S specifically.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check the availability for Les Misérables at the Morrison Center. Search for a group of 8 tickets specifically in 'Row R' or 'Row S'."
        ),
        queries=[[{
            "event_names": ["les miserables"], 
            "rows": ["r", "s"],
            "quantity": 8,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Boise",
        category="theater",
        tags=["theater", "row_search", "specific_seating"],
    ),
    TaskScenario(
        task_id="vividseats/theater/les_miserables/boise_mid_range",
        name="Les Miserables - Boise Mid-Range Price",
        description="Find tickets between $140 and $200 with the Main Floor filter.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Find me 8 tickets for Les Misérables in Boise. I want to spend at least $140 but not more than $200 per ticket. "
        ),
        queries=[[{
            "event_names": ["les miserables"], 
            "min_price": 140.0,
            "max_price": 200.0,
            "quantity": 8,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Boise",
        category="theater",
        tags=["theater", "price_range", "zone_filter"],
    ),
    TaskScenario(
        task_id="vividseats/sports/houston_rodeo/suites_zone_filter",
        name="Houston Rodeo - Suites Zone Check",
        description="Filter for Suite zones to find 4 tickets.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for tickets to the Houston Rodeo (Forrest Frank) at NRG Stadium. Use the zone filter to specifically show 'Suites' and find 4 tickets."
        ),
        queries=[[{
            "event_names": ["houston rodeo", "forrest frank"],
            "quantity": 4,
            "zones": ["suites"],
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Chicago",
        category="sports",
        tags=["rodeo", "houston", "zone_filter"],
    ),
    TaskScenario(
        task_id="vividseats/sports/houston_rodeo/budget_under_125",
        name="Houston Rodeo - Group Under $125",
        description="Find 4 tickets for the Rodeo priced under $125.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I'm looking for 4 tickets to the Houston Rodeo on March 8 priced strictly below $125 per ticket. Please find available options."
        ),
        queries=[[{
            "event_names": ["houston rodeo"],
            "dates": ["2026-03-08"],
            "quantity": 4,
            "max_price": 125.0, 
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Chicago",
        category="sports",
        tags=["rodeo", "budget", "group_tickets"],
    ),
    TaskScenario(
        task_id="vividseats/sports/houston_rodeo/section_874_verification",
        name="Houston Rodeo - Section 874 Check",
        description="Verify availability for 4 tickets in Section 874.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check the Vivid Seats listings for Forrest Frank at the Houston Rodeo. Find a group of 4 tickets specifically in Section 874."
        ),
        queries=[[{
            "event_names": ["houston rodeo", "forrest frank"],
            "sections": ["874"],
            "quantity": 4,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Chicago",
        category="sports",
        tags=["rodeo", "specific_section"],
    ),
    TaskScenario(
        task_id="vividseats/comedy/matt_rife/netflix_joke_fest_budget",
        name="Matt Rife - LA Fest Under $250",
        description="Find a single ticket for Matt Rife in LA under $250.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "I want to see Matt Rife at the Netflix Is A Joke Fest in Los Angeles. Find me a single ticket for the May 7th show that costs less than $250."
        ),
        queries=[[{
            "event_names": ["matt rife", "netflix is a joke"], 
            "cities": ["los angeles"],
            "dates": ["2026-05-07"],
            "quantity": 1,
            "max_price": 250.0,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="comedy",
        tags=["comedy", "netflix_fest", "budget"],
    ),
    TaskScenario(
        task_id="vividseats/comedy/matt_rife/floor_bench_premium",
        name="Matt Rife - Floor Bench Seating",
        description="Find a ticket specifically in the Floor Bench section.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Search for Matt Rife tickets at The Comedy Store. I'm looking for a more premium experience, so please find a ticket specifically in the 'Floor Bench' section."
        ),
        queries=[[{
            "event_names": ["matt rife"], 
            "sections": ["floor bench"],
            "quantity": 1,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="comedy",
        tags=["comedy", "premium_seating", "matt_rife"],
    ),
    TaskScenario(
        task_id="vividseats/comedy/matt_rife/comedy_store_min_price",
        name="Matt Rife - Comedy Store Price Range",
        description="Find a ticket between $260 and $300 at The Comedy Store.",
        url="https://www.vividseats.com/",
        task_prompt=(
            "Check the availability for Matt Rife in Los Angeles. I'm looking for a ticket at The Comedy Store priced between $260 and $300."
        ),
        queries=[[{
            "event_names": ["matt rife"], 
            "venues": ["the comedy store"],
            "min_price": 260.0,
            "max_price": 300.0,
            "quantity": 1,
            "require_available": True,
        }]],
        location="United States",
        timezone="America/Los_Angeles",
        category="comedy",
        tags=["comedy", "price_range", "specific_venue"],
    )


]

class BrowserManager:
    def __init__(self, config: BrowserConfig = None):
        self.config = config or BrowserConfig()
        self.browser = None
        self.context = None
        self.page = None
    
    async def launch(self, playwright) -> tuple:
        self.browser = await playwright.chromium.launch(headless=self.config.headless, args=self.config.launch_args)
        self.context = await self.browser.new_context(viewport={"width": self.config.viewport_width, "height": self.config.viewport_height}, user_agent=self.config.user_agent)
        
        # Anti-detection scripts (crucial for Cloudflare/PX on Vivid Seats)
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        self.page = await self.context.new_page()
        return self.browser, self.context, self.page
    
    async def close(self) -> None:
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()

class ResultReporter:
    """Formats and displays verification results for Vivid Seats."""
    
    @staticmethod
    def print_result(result, evaluator, scenario) -> None:
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)
        
        score_pct = result.score * 100
        status = "✅ PASS" if result.score >= 1.0 else "⚠️ PARTIAL" if result.score > 0 else "❌ FAIL"
        
        print(f"Status:           {status}")
        print(f"Score:            {score_pct:.1f}%")
        print(f"Queries Matched:  {result.n_covered}/{result.n_queries}")
        print(f"Pages Navigated:  {len(evaluator._navigation_stack)}")
        print("-" * 80)
        
        # Check for bot blocks (Cloudflare or PX)
        bot_blocks = [p for p in evaluator._navigation_stack if p.get("anti_bot") in ["blocked_perimeterx", "blocked_cloudflare"]]
        if bot_blocks:
            print("🚨 WARNING: Anti-Bot Block Detected during session! 🚨")
            print("-" * 80)

        for i, covered in enumerate(result.is_query_covered):
            status_icon = "✓" if covered else "✗"
            print(f"  Query {i+1}: [{status_icon}] {'Matched' if covered else 'Not matched'}")
        
        # Show scraped events for debugging
        print("-" * 80)
        print("EVENTS SCRAPED DURING SESSION:")
        all_events = []
        for page_infos in evaluator._all_infos:
            for event in page_infos:
                if event.get("eventName") and event.get("eventName") != "unknown" and event not in all_events:
                    all_events.append(event)
        
        if all_events:
            for i, event in enumerate(all_events[:15], 1):  # Show up to first 15 to avoid console spam
                name = event.get("eventName", "unknown").title()
                city = event.get("city") or "?"
                date = event.get("date") or "?"
                price = event.get("price")
                is_super_seller = event.get("isSuperSeller", False)
                source = event.get("source") or "?"
                
                price_str = f"${price}" if price else "?"
                seller_str = "🌟 Super Seller" if is_super_seller else "🎫 Standard Seller"
                print(f"  {i}. {name}")
                print(f"     📍 {city} | 📅 {date} | 💰 {price_str} | {seller_str} | 🔗 {source}")
        else:
            print("  No usable events scraped (Check if blocked by anti-bot or if JS needs selector updates)")
        
        print("=" * 80 + "\n")


async def run_scenario(scenario: TaskScenario) -> dict:
    evaluator = VividSeatsInfoGathering(queries=scenario.queries)
    reporter = ResultReporter() # <-- Initialize reporter
    
    print(f"\n{'='*60}\nTASK: {scenario.task_prompt}\n{'='*60}")
    input("Press ENTER to launch browser...")
    
    async with async_playwright() as p:
        browser_mgr = BrowserManager()
        browser, context, page = await browser_mgr.launch(p)
        
        await evaluator.reset()
        evaluator.attach_to_context(context)
        
        try:
            await page.goto(scenario.url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            logger.warning(f"Initial navigation warning: {e}")
            
        await asyncio.to_thread(input, "\nPress ENTER when you've completed the task... ")
        
        # Force a final scrape right before evaluation
        try:
            await evaluator.update(page=page)
        except Exception:
            pass
            
        result = await evaluator.compute()
        await browser_mgr.close()
    
    # <-- Print the detailed scraped results here
    reporter.print_result(result, evaluator, scenario) 
    return result

async def main():
    logger.remove()
    logger.add(sys.stderr, format="<level>{message}</level>", level="INFO")
    for i, s in enumerate(SCENARIOS, 1): print(f"[{i}] {s.name}")
    choice = input("\nSelect scenario index: ")
    if choice.isdigit() and 1 <= int(choice) <= len(SCENARIOS):
        await run_scenario(SCENARIOS[int(choice) - 1])

if __name__ == "__main__":
    asyncio.run(main())