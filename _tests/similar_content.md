---
title: "Content Similarity Algorithm Tests"
test_cases:
    - [drop-off_twomey-molly, raincoat_limon-ada]
    - [arts-of-living-on-a-damaged-planet, timefulness_bjornerud]
    - [baraka_fricke-ron, repetition_cooper-mcgloughlin]
    - [short-history-of-nearly-everything_bryson-bill, burden-of-proof_gladwell-m]
    - [sapiens_harari-y, world-until-yesterday_diamond-jared]
    - [citizen_rankine-claudia, carlos_gladwell-m]
    - [just-us_rankine-claudia, 1619]
    - [lao-buddhist-women_tsomo-karma-lekshe, traffic-in-heirarchy-keeler-ward]
    - [oral-transmission_wynne, oral-dimensions-of-pali_analayo]
    - [mindfulness-in-plain-english_gunaratana, how-to-meditate_yuttadhammo]
    - [how-to-meditate_yuttadhammo, instructions-to-insight-meditation_mahasi]
    - [what-work-is_levine-philip, you-can-have-it_levine-philip]
    - [rebirth-and-the-inbetween_sujato, when-does-human-life-begin_brahm]
    - [ordaining-renunciation_nirodha, going-forth_viradhammo]
    - [youre-not-a-bad-person_kashtan-miki, mindfulness-racial-bias_magee-rhonda]
    - [ptsd-in-the-slaughterhouse, you-can-have-it_levine-philip]
    - [unbearable_baskin-jon, limits-of-power_gladwell]
    - [behave_sapolsky-robert, challenges-of-the-disengaged-mind_wilson-et-al]
    - [mindfulness-intervention-to-youth-issues-in-vietnam_le-trieu, mindfulness-in-palestine_pigni-a]
    - [in-search-of-schrodingers-cat_gribbin-john, brief-history-of-time_hawking]
    - [venerated-objects-early-buddhism_harvey, lotus-as-symbol_olson_carl]
    - [altruism-in-classical-buddhism_lewis-todd, cultivation-of-virtue_fink-charles]
    - [against-the-defilements_suchart, kammatthana_mahabua]
    - [buddhist-wheel-symbol_karunaratne, venerated-objects-early-buddhism_harvey]
    - [understanding-the-chinese-buddhist-temple_negru-john, popular-deities-in-chinese-buddhism_kuanming]
    - [sn_bodhi, sn_sujato]
    - [an_bodhi, an_sujato]
    - [the-buddhist-layman, simple-guide-to-life_bogoda-r]
    - [buddhist-hybrid-english_griffiths-paul, philological-approach_norman]
    - [tracing-thought-through-things_stargardt, authenticity_sujato-brahmali]
    - [authenticity_sujato-brahmali, hoary-past-hazy-memory_hinuber-oskar-v]
    - [buzz-buzz-buzz_michelle-nijhuis, should-trees-have-standing_stone-chris]
    - [twenty-three-percent, sexual-consent_popova]
    - [sexual-consent_popova, what-every-body-is-saying_navarro-joe]
    - [compassionate-killing_gethin, trolly-car-dilemma_pandita]
    - [historical-authenticity_wynne, authenticity_sujato-brahmali]
    - [did-the-buddha-exist_wynne, in-search-of-the-real-buddha_harvey]
    - [giving-makes-us-happy, meditation-moral-obligation_vox]
    - [kids-these-days_harris-malcolm, debt_graeber-david]
    - [mn044, bhikkhuni-dhammadinna_analayo]
    - [teardrops-of-time_fuhrmann-arnika, i-lost-you_kalayanapong-angkarn]
    - [shared-characters-in-jain-buddhist-and-hindu-narrative_appleton, story-of-the-horse-king_appleton]
    - [politics-of-tourism-in-asia_richter-linda, battling-the-buddha-of-love_falcone-jessica]
    - [piranesi_clarke-susanna, no-one-belongs-here-more-than-you_july-miranda]
    - [yasodhara_sasson-v, wife-and-son_gindin-matthew]
    - [rewriting-buddhism_gornall-alastair, idea-of-the-pali-canon_collins-steven]
    - [chithurst-story_sharp-george, comes-to-sussex_bbc]
    - [kalmyks_dhammika, siberian-revival_journeyman]
    - [map-of-jambudipa, maps-of-ancient-india_anandajoti]
partial_cases:
    - [rewriting-buddhism_gornall-alastair, idea-of-the-pali-canon_collins-steven]
    - [giving-makes-us-happy, meditation-moral-obligation_vox]
    - [kalmyks_dhammika, siberian-revival_journeyman]
    - [the-buddhist-layman, simple-guide-to-life_bogoda-r]
    - [mindfulness-in-plain-english_gunaratana, how-to-meditate_yuttadhammo]
    - [venerated-objects-early-buddhism_harvey, lotus-as-symbol_olson_carl]
---

A series of integration tests for the quality of the content recommendations.

{%- assign cases = page.test_cases -%}
{%- if site.partial_build -%}
{%- assign cases = page.partial_cases -%}
{%- endif -%}
{%- assign succs = 0 -%}
{%- assign fails = 0 -%}
{% assign simcount = 0 %}

| Test Name | Status  |  Notes |
|-----------|---------|--------|{% for test in cases %}{% assign fc = site.content | find: "slug", test[0] %}{% assign sc = site.content | find: "slug", test[1] %}{% capture cont_req %}{% assign include_content = fc %}{% similar_content %}{% endcapture %}
| "[{{ fc.title | split: ':' | first }}]({{ fc.url }})" should recommend "[{{ sc.title | split: ':' | first }}]({{ sc.url }})" <details><code>{{ cont_req | strip_html | strip_newlines }}</code></details> | {% if cont_req contains test[1] %}{% assign succs = succs | plus: 1 %}Pass ✅{% else %}{% assign fails = fails | plus: 1 %}FAIL ❌{% endif %}  | of {% assign c = cont_req | split: "</li>" | size | minus: 2 %}{% assign simcount = simcount | plus: c %}{{ c }}  |{% endfor %}
|-----|------|----|
| Totals: | {{ succs }} Pass and {{ fails }} Failed | {{ simcount }} total recommendations |

