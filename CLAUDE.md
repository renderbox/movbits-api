# microdrama-site — Django REST Framework Backend

## Role
Django REST Framework backend API for Movbits, serving the movbits-app frontend.

## Related repos
- `Movbitsapp/` — source of truth for UI shape and expected data contracts
- `movbits-app/` — frontend consumer of this API

## App file structure
API-related files are scoped inside each Django app under an `api/` subdirectory.
Always follow this pattern — never place views, serializers, or urls at the app root.

Example:
```
src/
└── some_app/
    ├── models.py
    ├── admin.py
    └── api/
        ├── __init__.py
        ├── serializers.py
        ├── views.py
        └── urls.py
```

When adding a new endpoint:
1. Identify the correct existing app (or confirm with developer if a new app is needed)
2. Create or edit files inside that app's `api/` directory only
3. Register urls in that app's `api/urls.py`, then include in the project `urls.py`

## Serializer field names
- Serializer field names must match the data shape extracted from the Movbitsapp component
- Any field name change is a breaking change — audit movbits-app/src/api/clients/ before making it
- If a mismatch between the component shape and an existing serializer is found,
  flag it with ⚠️ and wait for developer instruction — do not silently rename fields

## Scaffolding workflow (for missing endpoints)
When an endpoint doesn't exist yet (🚧 MISSING):
1. Extract the data shape from the relevant Movbitsapp component
2. Create the serializer to match that shape exactly
3. Build a stub view that returns hardcoded data matching the serializer shape
4. Wire up urls following the app file structure pattern above
5. Confirm with the developer that the shape and scaffold are correct
6. Only write real queryset/read logic after developer confirms the scaffold
