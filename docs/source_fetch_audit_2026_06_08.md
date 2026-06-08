# Source Fetch Audit

- baseline knowledge docs: 53
- stage0 active count: 10
- stage0 active cap: 10
- policy: freeze current Stage 0; classify new sources as candidate until a promotion/replacement decision is reviewed

| Source | Stage | Active | Decision | Official status | Raw status | Warning |
| --- | --- | ---: | --- | --- | --- | --- |
| `graduation_biochemistry_requirements` | stage0 | true | retain | verified | 200 | fetch failed; reused cached raw snapshot: ReadTimeout |
| `graduation_curriculum_pdf` | stage0 | true | retain | verified | 200 | fetch failed; reused cached raw snapshot: ReadTimeout |
| `graduation_english_requirements` | stage0 | true | retain | verified | 200 |  |
| `academic_notice_board` | stage0 | true | retain | verified | 200 | freshness policy: latest_snapshot; fetch failed; reused cached raw snapshot: ReadTimeout |
| `academic_notice_detail_2511200` | stage0 | true | retain | verified | 200 | freshness policy: latest_snapshot; fetch failed; reused cached raw snapshot: ConnectionError |
| `academic_notice_detail_2512124` | stage0 | true | retain | verified | 200 | freshness policy: latest_snapshot; fetch failed; reused cached raw snapshot: ConnectionError |
| `academic_notice_detail_2512782` | stage0 | true | retain | verified | 200 | freshness policy: latest_snapshot; fetch failed; reused cached raw snapshot: ConnectionError |
| `academic_calendar` | stage0 | true | retain | verified | 200 | fetch failed; reused cached raw snapshot: ConnectionError |
| `cnu_mobile_food` | stage0 | true | retain | official_linked | 200 | source is not official-chain verified; freshness policy: short_ttl |
| `shuttle_bus` | stage0 | true | retain | verified | 200 | fetch failed; reused cached raw snapshot: ConnectionError |
| `graduation_energy_requirements` | stage1 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `graduation_horticulture_counsel` | stage1 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `notice_energy_academic` | stage1 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `academic_calendar_dance` | stage1 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `shuttle_geo_notice_2026` | stage1 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `dining_mobile_candidate` | stage1 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `curriculum_2025_pdf_candidate` | stage2 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `sugang_entry_2025_pdf` | stage2 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `academic_calendar_cic` | stage2 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `dining_plus_welfare_candidate` | stage2 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
| `shuttle_plus_main_candidate` | stage2 | false | defer | unverified | not fetched | official-chain evidence is missing or insufficient |
