# Restructuring this django project


so I started this project based on the legacy code (see ea-cli/ submodule), but we might want to restructure it to remove the dependency on the legacy code and make it more modular and reduce errors. This is mainly centered around the complicated logic for updating DB from sheets (faculty / raw).

updating DB status for items when ingesting sheets from qlik or faculty entry is now made pretty difficult, we have to compare all kinds of statuses and fields each time because we update in bulk and we don't have a clear way to know what changed; or what has priority.

as we're moving towards a dashboard/app that directly interacts with the db instead of making sheets, which should let us remove a lot of this logic. That will also let us remove some models/fields and simplify the code.

New proposed structure/models/functions/pipeline idea:

### INGESTION

- we create separate models for FacultyEntry and QlikEntry to hold directly the raw data ingested from those sources, each should have a datetime field for when it was ingested
- maybe also have a model that groups those entries by ingestion date, so we can keep track of different ingestions, e.g. FacultyIngestion, QlikIngestion that holds a datetime and a foreign key to multiple FacultyEntry / QlikEntry or something, along with the eventually processed & written changes to the main items in the database
- for each ingestion, we read in the sheets, parse/clean them lightly if required (also see next step), then create the new entries in the DB for storage
    - [optimization] if identical data already exists, we can skip creating the entry (==all fields identical). howvever, if we make any errors in this comparison, we might miss/overwrite changes so this needs to be done carefully
    - also think about when to store this data in terms of cleaning/parsing -- do we want to store the raw data as-is, or cleaned data? include the db specific added fields (e.g. workflow status) or not? maybe better to store as raw as possible, and do cleaning/adding fields in the next step?
- we should also create commands to run these ingestions from cli/dasboard/admin, so we dont necessarily have to run the full ingestion pipeline each time

### FROM RAW TO CLEAN
- after ingestion of the raw data, depending on the type we will normalize/standardize the data and add db specific fields, like workflow status, mapping faculties to departments, parse enums, etc. This should be heavily tested/verified so we don;'t introduce errors here

### PROCESSING / UPDATING
- then we have a processing step for each type of ingestion (faculty/qlik) that compares the new entries with the existing items in the DB, and determines what changes need to be made
    - this processing step should be modular, so we can easily update the logic for how we determine changes
    - we can also log the changes that will be made, so we have a record of what was changed and why -- maybe it's good to add this to the FacultyIngestion / QlikIngestion models. either as a json field or a separate ChangeLog model that links to the ingestion
- we can redo the processing pipeline by making some assumptions:
    -  qlik items are either new (not in db) or existing (in db + sheets).
        - if new: just add them fully
        - if existing: only update a specific set of specific fields -- most will not change!
        - faculty data is always higher prio for classification / workflow status
    - faculty entries can never be new, only update existing data
        - [old version] each item should only exist accross all sheets in a single faculty ingestion
        - we only need to update changeable fields (classification fields + workflow status + remarks)
        - the biggest issue was figuring out if we needed to update the DB status based on sheets, but now that we move away from sheets we can directly set it without worrying about conflicts
    - we also want some overwrite function that lets us load in corrected data for specific items, ignoring existing data -- this can be a special mode in the processing step. point to a sheet/csv with item ids and corrected data, and it will just update those items directly, overwriting any existing data
        - we need to make sure this isn't then overwritten by future ingestions, so maybe we add a "last corrected" timestamp field to the items that we check during processing -- if the ingestion is older than the last corrected timestamp, we skip updating those fields -- or something? or set a flag that indicates manual correction? dunno. lower prio.

### ENRICHMENT

- after all of that, or even completely separately, we can have an enrichment step that adds additional data from OSIRIS, people pages, pdf parsing, etc.
- this should be modular, so we can easily add/remove enrichment sources
- maybe we should also log the enrichment actions taken, so we have a record of what was added/changed and why? dunno if we need that.
- in terms of structure, make sure most of this enrichment logic is separate, but also in the model layer -- so store this type of data in m2m or fk related models, so we can easily query/filter based on enriched data and not have everything in a single flat model

### CLASSIFICATION
- we want to add our own classification (suggestion) model as well, that uses the available data to suggest classifications for items
- should run separately as well, best as a background task actually
- preferably after the enrichment step, so we have more data to base the classification on, but could be forced to run earlier if needed

### DASHBOARD

- replaces the excel files
- allows direct interaction with the DB items, updating status, classification, remarks, etc.
- see ea-cli/dashboard for legacy dashboard code
- should also allow triggering ingestions, processing, enrichment, classification tasks from the UI
- should have proper user auth/permissions, so only authorized users can make changes
- should log all changes made via the dashboard, so we have an audit trail of who changed what and when
- also add filtering, searching, exporting functionality to the dashboard, so users can easily find and work with items
- also export/import functionality to allow bulk updates via csv/xlsx


## Priority

We need to redo our priorities a bit. We first want to basically get the ingestion pipeline working well, including the overwrite functionality, and bolt-on the legacy export functions so we can at least produce the required excel files for now while we don't have the dashboard ready. This should let us replace a large part of the existing codebase while keeping the old functionality and user workflow intact.
Then we'll add the enrichment (as that's also currently part of the existing codebase).
Then we move to the dashboard: this should replace the excel files and allow direct interaction with the DB, making future ingestions/enrichments/classifications easier to manage.
Finally we combine all of the available data + ML to make classification suggestions as an additional feature.

So split in three phases:

### PHASE A: CORE FUNCTIONALITY
1. ingestion models + ingestion commands
2. ingestion pipeline (raw -> clean -> process)
3. legacy export functions (excel sheets per faculty to adhere to existing workflow)
4. hard overwrite functionality

### PHASE B: NICE TO HAVE
5. enrichment

### PHASE C: NEW FUNCTIONALITY
6. dashboard
7. classification

Each phase should be properly tested and verified before moving to the next, to ensure we don't introduce errors or break existing functionality. We especially want to make sure the ingestion and processing logic is solid, as that's the core of the system. We should test it on various edge cases and data scenarios to ensure it handles everything correctly, using real data where possible.


## Compared to current codebase status

We've been moving a bit too fast, already diving into various enrichment and classification features without having a solid ingestion and processing pipeline in place. This has led to a lot of complicated code and potential errors, as we have to constantly check and re-check statuses and fields when updating the DB from sheets.
We need to take a step back and focus on getting the core functionality right first, before adding more features on top. This will make the codebase cleaner, more modular, and easier to maintain in the long run. Below is a quick list of modules in the current codebase, and what we should do with them:

src/config/ - ensure this is all correct, and all required settings as found in the legacy code (ea-cli/easy-access/settings.py) are ported over

src/apps/api - ignore for now, phase C
src/apps/classification - ignore for now, phase C
src/apps/dashboard - ignore for now, phase C
src/apps/enrichment - ignore for now, phase B
src/apps/documents - ignore for now, phase B
src/apps/core - main focus along with ingest, needs to be redone/updated/tested as per above
src/apps/ingest - main focus along with core, needs to be redone/updated/tested as per above. Check the contents to see if any code is out of scope, and place it in the correct subapp
