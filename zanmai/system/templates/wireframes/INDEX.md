# Wireframe library

Neutral greyscale slides. Theme colours and theme fonts only, so taking one into a
brand is a theme swap, not a rebuild. One line per pattern; the detail is in
`library.json`, the picture in `previews/`.

| # | id | what it is | fits | flex | view |
|---|---|---|---|---|---|
| 1 | `cards-row` | Row of cards | a set of items of the same kind, listed side by side | cards 3 (2-4) | screen |
| 2 | `cards-row-kicker` | Row of cards with a kicker line | the kicker names the context the slide belongs to - a section, a topic, a client | cards 3 (2-4); kicker 1 (0-1) | screen |
| 3 | `cards-row-room` | Row of cards, room size | the card row for a slide shown on a wall rather than a screen | cards 3 (2-3) | room |
| 4 | `path-milestones` | Path with milestones | steps that follow one another in time | stations 4 (3-6) | screen |
| 5 | `chevron-stages` | Chevron stages | a sequence where each stage hands over to the next | stages 4 (3-6) | screen |
| 6 | `snake-cards` | Cards in two rows, read back and forth | six steps that do not fit in one row | per_row 3 (2-4); rows 2 (2-2) | screen |
| 7 | `staircase` | Staircase of steps | stages that build on each other and get bigger, later or more advanced | steps 4 (3-5) | screen |
| 8 | `hub-satellites` | Hub with satellites | one thing and the parts that feed into it | satellites 6 (4-6) | screen |
| 9 | `pyramid-levels` | Pyramid of levels | levels that build on one another - a maturity model, a hierarchy of needs | levels 4 (3-5) | screen |
| 10 | `funnel-stages` | Funnel with a list on each side | something that loses volume at every step | stages 4 (3-5); side_lists 2 (0-2) | screen |
| 11 | `matrix-axes` | Matrix with named axes | two dimensions crossed - effort against value, performance against potential | columns 3 (2-3); rows 2 (2-3) | screen |
| 12 | `quad-matrix` | Four quadrants | two yes/no dimensions crossed - urgent against important, effort against value | quadrants 4 (4-4); axis_labels 2 (0-2) | screen |
| 13 | `big-numbers` | Wall of key figures | measured results - counts, shares, durations, money | figures 4 (2-5) | room |
| 14 | `comparison-columns` | Two columns compared row by row | two options weighed against each other on the same criteria | rows 4 (3-6); columns 2 (2-3) | screen |
| 15 | `split-media-text` | Media on one side, text on the other | anything that has a picture - a product, a place, a person, a screenshot | bullets 3 (0-4); media_share 0.48 (0.35-0.6) | screen |
| 16 | `statement` | One statement | the one thing the audience should remember | statement_chars 175 (60-240) | room |
| 17 | `timeline-agenda` | Agenda with a key column | an agenda, a schedule, a plan with times | entries 3 (3-4) | screen |
| 18 | `text-two-columns` | Text in two columns | a slide that has to carry real prose - a position, an explanation, a summary | columns 2 (2-3); lead 1 (0-1) | screen |
| 19 | `status-table-timeline` | Status table with timeline bars | a list of items each with an owner, a state and a duration | body_rows 4 (3-6); text_columns 4 (3-4); time_columns 4 (0-6); legend_items 3 (2-4) | screen |
| 20 | `pie-callouts` | Chart with callout cards | a split of one whole into parts, where each part needs a sentence | segments 4 (3-4); chart_type doughnut (doughnut-pie) | screen |
| 21 | `bars-compare` | Bar chart with readings | measured values across categories, two series compared | series 2 (1-3); categories 4 (3-6); readings 3 (1-3) | screen |
| 22 | `zones-chain` | Chain across two zones | a process that crosses a border - two companies, two systems, two countries | steps_per_zone 3 (2-3); chips 3 (0-4); closing_bar 1 (0-1) | screen |
| 23 | `cards-bullets` | Cards carrying a list | a set of areas, each with the things it contains | cards 4 (2-4); bullets_per_card 4 (2-5) | screen |
| 24 | `capability-matrix` | Bands of tiles with a side label | a portfolio read on two axes at once - areas across, layers down | bands 3 (3-4); tiles_per_band 4 (2-5); closing_band 1 (0-1) | screen |
| 25 | `statement-kpi-media` | Claim, figures and a picture area | who we are and the numbers that prove it | figures 3 (2-4); claim_lines 3 (1-3); media_share 0.5 (0.4-0.6) | room |
| 26 | `quad-loop` | Four blocks in a loop | four areas that belong to one cycle rather than a straight sequence | blocks 4 (3-4); lines_per_block 3 (2-5) | screen |
| 27 | `case-study-facts` | Case study with a fact card | one customer, one project, one story - with the hard facts beside it | facts 4 (3-6); card_side right (left-right) | screen |
| 28 | `quote-wall` | Wall of quotes | what other people say - customers, staff, partners | quotes 3 (2-4); offset 1 (0-1) | screen |
| 29 | `media-legend` | Picture area with a numbered legend | anything where a picture carries markers that need naming | entries 5 (3-6); media_share 0.6 (0.45-0.7) | screen |
| 30 | `feature-columns` | Options as columns, criteria as rows | several options measured on the same criteria | options 4 (2-5); criteria 4 (3-7); foot_band 1 (0-1) | screen |
| 31 | `butterfly-bars` | Bars growing away from a shared centre | two things measured on the same scale, row by row | rows 5 (3-7); sides 2 (2-2) | screen |
| 32 | `two-tables-total` | Two blocks of figures and a total | a calculation shown as its parts and its outcome | blocks 2 (1-2); rows_per_block 4 (3-6); total_rows 2 (1-3) | screen |
| 33 | `tile-grid` | Grid of tiles with a picture area | a portfolio, a product range, a set of services - things that are equal in rank | columns 4 (3-5); rows 2 (1-3) | screen |
| 34 | `logo-grid` | Wall of logo areas | partners, customers, tools, certifications - a wall that says how many | columns 6 (4-8); rows 4 (2-5) | screen |
| 35 | `list-detail` | List on the left, one thing spelled out on the right | the points of an offer, with one of them broken open beside it | points 4 (3-5); levels 4 (2-5); panel_share 0.42 (0.3-0.5) | screen |
| 36 | `title-slide` | Title slide | the first slide of a deck | title_lines 2 (1-3); kicker 1 (0-1); media_share 0.44 (0-0.6) | room |
| 37 | `agenda-numbered` | Agenda with numbers | the agenda of a deck, or a summary of what was covered | chapters 5 (3-7); context_line 1 (0-1) | room |
| 38 | `section-divider` | Section divider | the break between two parts of a deck | number 1 (0-1); summary_line 1 (0-1); media_share 0.4 (0-0.55) | room |
| 39 | `closing-contact` | Closing slide with contact details | the last slide of a deck | contact_lines 3 (2-5); code_area 1 (0-1); media_share 0.44 (0-0.6) | room |
| 40 | `person-profile` | Person profile | one person: a speaker, an expert, a contact, a new colleague | facts 4 (2-6); portrait_share 0.35 (0.25-0.45) | screen |
| 41 | `team-row` | Row of people | the people on a project, a team, a panel, a board | people 4 (2-5); description_line 1 (0-1) | screen |
| 42 | `table-findings` | Table, findings, and the sentence underneath | a comparison where one row is us, or one row is the point | rows 6 (4-8); columns 4 (3-5); findings 3 (2-4); footer_band 1 (0-1) | screen |
| 43 | `chart-findings` | Chart, findings, and the sentence underneath | a development over time with what it means beside it | findings 2 (1-3); footer_band 1 (0-1); chart_type line (line-column) | screen |
| 44 | `label-value-blocks` | Label and value blocks | a fact sheet: project, owner, budget, deadline, scope, risk | blocks 6 (2-8); columns 2 (1-3); label_share 0.32 (0.2-0.4) | screen |
| 45 | `statement-tiles` | Claim beside a group of tiles | one sentence that holds for everything in the group | tiles 5 (3-6); claim_share 0.27 (0.2-0.35); tab 1 (0-1) | screen |
| 46 | `cycle-segments` | Cycle with numbered stages | stages that come back round - a customer journey, a review cycle, a season | stages 6 (4-8); centre_label 1 (0-1) | screen |
| 47 | `claim-tree` | One claim, the things that carry it | a conclusion and what it rests on | supports 4 (2-5); head_lines 2 (1-3) | screen |
| 48 | `grouped-measures` | Grouped measures with priority and owner | a plan: what is to be done, how urgent, and by whom | groups 3 (2-5); rows_per_group 2 (1-4); priority_levels 4 (2-4); owner_column 1 (0-1) | screen |
| 49 | `bullet-list` | Points with a heading each | the plainest way to make several points on one slide | points 5 (3-6); headings 1 (0-1) | screen |
| 50 | `bullet-list-two-columns` | Points in two columns | eight points that belong together and do not fit in one column | points_per_column 4 (3-5); columns 2 (2-3); column_headings 0 (0-1) | screen |
| 51 | `title-and-table` | Title and a plain table | figures that belong in rows and columns and need no picture | rows 5 (3-7); columns 4 (2-6) | screen |
| 52 | `image-full` | One picture, full width | a screenshot, a photograph, a diagram made elsewhere | caption 1 (0-1); source_line 1 (0-1) | room |
| 53 | `title-only` | Title, intro and a free area | the fallback when nothing else fits: a screenshot, a pasted chart, a drawing | intro 1 (0-1) | screen |
| 54 | `question-answer` | A question and the answers to it | a slide that opens a discussion rather than closing one | answers 3 (2-4); question_lines 2 (1-3) | screen |
| 55 | `offer-two-blocks` | Offer: two blocks, results, terms | one offer on one slide: the situation, what happens, what comes out, what it costs | blocks 2 (2-3); bullets_per_block 3 (2-4); result_items 4 (3-5); terms 3 (2-4) | screen |
| 56 | `timeline-phases` | Phases with headings above the line | a sequence where every step needs two or three sentences, not a label | phases 4 (3-5); footnote 1 (0-1); subtitle 1 (0-1) | screen |
| 57 | `numbered-sections` | Numbered sections stacked | three areas that each need several lines - a quarterly review, a status report | sections 3 (2-4); lines_per_section 3 (2-4) | screen |
| 58 | `media-feature-grid` | Picture area with a feature grid | a product or a screen with the four things worth saying about it | features 4 (2-6); columns 2 (1-2); media_share 0.42 (0.3-0.55) | screen |
