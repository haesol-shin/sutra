# Source Fetch Audit

- baseline knowledge docs: 53
- stage0 active count: 10
- stage0 active cap: 10
- policy: freeze current Stage 0; classify new sources as candidate until a promotion/replacement decision is reviewed

| Source | Stage | Active | Decision | Official status | Raw status | Warning |
| --- | --- | ---: | --- | --- | --- | --- |
| `graduation_biochemistry_requirements` | stage0 | true | retain | verified | 200 |  |
| `graduation_curriculum_pdf` | stage0 | true | retain | verified | 200 |  |
| `graduation_english_requirements` | stage0 | true | retain | verified | 200 |  |
| `academic_notice_board` | stage0 | true | retain | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_detail_2511200` | stage0 | true | retain | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_detail_2512124` | stage0 | true | retain | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_detail_2512782` | stage0 | true | retain | verified | 200 | freshness policy: latest_snapshot |
| `academic_calendar` | stage0 | true | retain | verified | 200 |  |
| `cnu_mobile_food` | stage0 | true | retain | verified | 200 | freshness policy: short_ttl |
| `shuttle_bus` | stage0 | true | retain | verified | 200 |  |
| `graduation_energy_requirements` | stage1 | false | defer | verified | 200 |  |
| `graduation_curriculum_2023_pdf` | stage1 | true | defer | verified | 200 |  |
| `graduation_curriculum_2024_pdf` | stage1 | true | defer | verified | 200 |  |
| `graduation_horticulture_counsel` | stage1 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `notice_energy_academic` | stage1 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `academic_calendar_dance` | stage1 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `academic_calendar_2023` | stage1 | true | defer | verified | 200 |  |
| `academic_calendar_2024` | stage1 | true | defer | verified | 200 |  |
| `academic_calendar_2025` | stage1 | true | defer | verified | 200 |  |
| `academic_calendar_2026` | stage1 | true | defer | verified | 200 |  |
| `course_registration_notice_2026` | stage1 | true | defer | verified | 200 |  |
| `shuttle_geo_notice_2026` | stage1 | false | defer | verified | 200 |  |
| `course_registration_plan_2025_2_pdf` | stage1 | true | defer | verified | 200 |  |
| `shuttle_geo_notice_2026` | stage1 | true | defer | verified | 200 |  |
| `dining_operation_notice_2507684` | stage1 | true | defer | verified | 200 |  |
| `homepage_academic_calendar_module` | stage1 | true | defer | verified | 200 |  |
| `cnu_mobile_food_week_2026_06_08_1st` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_08_2nd` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_08_3rd` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_08_4th` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_08_life_science` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `scholarship_overview` | stage1 | true | defer | verified | 200 |  |
| `dining_mobile_candidate` | stage1 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `scholarship_external_overview` | stage1 | true | defer | verified | 200 |  |
| `student_loan_overview` | stage1 | true | defer | verified | 200 |  |
| `english_ability_criteria` | stage1 | true | defer | verified | 200 |  |
| `english_ability_notice_2025_1_pdf` | stage1 | true | defer | verified | 200 |  |
| `registration_overload_faq` | stage1 | true | defer | verified | 200 |  |
| `graduation_energy_requirements` | stage1 | true | defer | verified | 200 |  |
| `graduation_law_requirements` | stage1 | true | defer | verified | 200 |  |
| `academic_calendar_english_education_undergrad` | stage1 | true | defer | verified | 200 |  |
| `graduation_vetmed_requirements` | stage1 | true | defer | verified | 200 |  |
| `graduation_chemistry_credit` | stage1 | true | defer | verified | 200 |  |
| `graduation_chemistry_teaching` | stage1 | true | defer | verified | 200 |  |
| `academic_notice_board_page_2` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_board_page_3` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_board_page_4` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_board_page_5` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_board_page_6` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `cnu_mobile_food_week_2026_06_01_1st` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_01_2nd` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_01_3rd` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_01_4th` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_01_life_science` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_15_1st` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_15_2nd` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_15_3rd` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_15_4th` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_15_life_science` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_22_1st` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_22_2nd` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_22_3rd` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_22_4th` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_22_life_science` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_29_1st` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_29_2nd` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_29_3rd` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_29_4th` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `cnu_mobile_food_week_2026_06_29_life_science` | stage1 | true | defer | verified | 200 | freshness policy: short_ttl |
| `notice_candidate_chemistry_0` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_chemistry_10` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_chemistry_20` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_chemistry_30` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_chemistry_40` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_chemistry_50` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_chemistry_60` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_chemistry_70` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_chemistry_80` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_chemistry_90` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_ai_0` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_ai_10` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_ai_20` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_ai_30` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_ai_40` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_ai_50` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_ai_60` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_ai_70` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_ai_80` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_ai_90` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_computer_0` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_computer_10` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_computer_20` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_computer_30` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_computer_40` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_computer_50` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_computer_60` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_computer_70` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_computer_80` | stage1 | true | defer | verified | 200 |  |
| `notice_candidate_computer_90` | stage1 | true | defer | verified | 200 |  |
| `academic_notice_candidate_page_7` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_8` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_9` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_10` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_11` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_12` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_13` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_14` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_15` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_16` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_17` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_18` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_19` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_20` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_21` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_22` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_23` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_24` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_25` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_26` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_27` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_28` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_29` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_30` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_31` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_32` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_33` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_34` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_35` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `academic_notice_candidate_page_36` | stage1 | true | defer | verified | 200 | freshness policy: latest_snapshot |
| `curriculum_2025_pdf_candidate` | stage2 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `sugang_entry_2025_pdf` | stage2 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `academic_calendar_cic` | stage2 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `dining_plus_welfare_candidate` | stage2 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `shuttle_plus_main_candidate` | stage2 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
