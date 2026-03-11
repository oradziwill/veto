# Adding Features

This guide explains the standard pattern for adding a new feature to Veto. It covers the full stack: Django model → migration → API → frontend.

---

## 1. Backend: New Django app

Only create a new app if the feature doesn't belong in an existing one (`billing`, `clients`, `patients`, `appointments`, `tenancy`).

```bash
cd backend
./venv/bin/python manage.py startapp myfeature apps/myfeature
```

Register it in `config/settings_base.py`:

```python
LOCAL_APPS = [
    ...
    "apps.myfeature",
]
```

---

## 2. Backend: Model

Create `apps/myfeature/models.py`:

```python
from django.db import models
from apps.tenancy.models import Clinic


class MyModel(models.Model):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="mymodels")
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
```

**Always include `clinic` ForeignKey** — this is what scopes data per tenant.

---

## 3. Backend: Migration

```bash
cd backend
./venv/bin/python manage.py makemigrations myfeature
./venv/bin/python manage.py migrate
```

Check the generated migration file before committing — make sure it has the right dependencies.

### Adding a field to an existing model

```bash
# Edit the model, then:
./venv/bin/python manage.py makemigrations billing  # or whichever app
./venv/bin/python manage.py migrate
```

For nullable fields, add `null=True, blank=True` to avoid requiring a default in the migration. For required fields with existing rows, you must provide a `default=`.

---

## 4. Backend: Serializer

Create `apps/myfeature/serializers.py`:

```python
from rest_framework import serializers
from .models import MyModel


class MyModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyModel
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]
```

If you need different serializers for read vs write (e.g. nested reads, flat writes):

```python
class MyModelReadSerializer(serializers.ModelSerializer):
    related_detail = RelatedSerializer(source="related", read_only=True)

    class Meta:
        model = MyModel
        fields = ["id", "name", "related_detail", "created_at"]


class MyModelWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyModel
        fields = ["name", "related"]
```

---

## 5. Backend: ViewSet

Create `apps/myfeature/views.py`:

```python
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import MyModel
from .serializers import MyModelSerializer


class MyModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MyModelSerializer

    def get_queryset(self):
        # Always scope to the current user's clinic
        return MyModel.objects.filter(clinic=self.request.user.clinic)

    def perform_create(self, serializer):
        serializer.save(clinic=self.request.user.clinic)
```

### Custom action

```python
from rest_framework.decorators import action
from rest_framework.response import Response

class MyModelViewSet(viewsets.ModelViewSet):
    ...

    @action(detail=True, methods=["post"], url_path="do-something")
    def do_something(self, request, pk=None):
        obj = self.get_object()
        # ... do work ...
        return Response({"status": "ok"})
```

Accessible at `POST /api/myfeature/<id>/do-something/`.

---

## 6. Backend: URLs

Create `apps/myfeature/urls.py`:

```python
from rest_framework.routers import DefaultRouter
from .views import MyModelViewSet

router = DefaultRouter()
router.register("mymodels", MyModelViewSet, basename="mymodel")

urlpatterns = router.urls
```

Register in `config/urls.py`:

```python
urlpatterns = [
    ...
    path("api/myfeature/", include("apps.myfeature.urls")),
]
```

---

## 7. Backend: Tests

Create `apps/myfeature/tests/test_mymodel.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from apps.myfeature.models import MyModel
from apps.tenancy.models import Clinic

User = get_user_model()


@pytest.fixture
def clinic(db):
    return Clinic.objects.create(name="Test Clinic")


@pytest.fixture
def user(db, clinic):
    u = User.objects.create_user(username="doc", password="pass")
    u.clinic = clinic
    u.save()
    return u


@pytest.mark.django_db
def test_create_mymodel(user, clinic):
    obj = MyModel.objects.create(clinic=clinic, name="Test")
    assert obj.id is not None
    assert obj.name == "Test"
```

Run tests:

```bash
cd backend
./venv/bin/pytest
```

---

## 8. Frontend: API service

Add to `frontend/src/services/api.js`:

```js
export const myFeatureAPI = {
  list: (params) => api.get('/myfeature/mymodels/', { params }),
  get: (id) => api.get(`/myfeature/mymodels/${id}/`),
  create: (data) => api.post('/myfeature/mymodels/', data),
  update: (id, data) => api.put(`/myfeature/mymodels/${id}/`, data),
  delete: (id) => api.delete(`/myfeature/mymodels/${id}/`),
  doSomething: (id) => api.post(`/myfeature/mymodels/${id}/do-something/`),
}
```

---

## 9. Frontend: Tab component

Create `frontend/src/components/tabs/MyFeatureTab.jsx`:

```jsx
import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { myFeatureAPI } from '../../services/api'
import './Tabs.css'

const MyFeatureTab = () => {
  const { t } = useTranslation()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchItems = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await myFeatureAPI.list()
      setItems(res.data.results || res.data)
    } catch {
      setError(t('myfeature.loadError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchItems() }, [])

  return (
    <div className="tab-container">
      <div className="tab-header">
        <h2>{t('myfeature.title')}</h2>
      </div>
      <div className="tab-content-wrapper">
        {loading && <div className="loading-message">{t('common.loading')}</div>}
        {error && <div className="error-message">{error}</div>}
        {!loading && !error && (
          <div className="inventory-table">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t('myfeature.name')}</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default MyFeatureTab
```

---

## 10. Frontend: Register the tab

In `frontend/src/App.jsx` (or wherever tabs are rendered), add the new tab to the nav and render it:

```jsx
import MyFeatureTab from './components/tabs/MyFeatureTab'

// In the tab nav:
<button onClick={() => setActiveTab('myfeature')}>{t('nav.myfeature')}</button>

// In the tab render:
{activeTab === 'myfeature' && <MyFeatureTab />}
```

---

## 11. Frontend: Translations

Add keys to `frontend/src/locales/en.json` and `pl.json`:

```json
{
  "myfeature": {
    "title": "My Feature",
    "name": "Name",
    "loadError": "Failed to load items. Please try again."
  }
}
```

---

## Checklist

- [ ] Model has `clinic` ForeignKey for multi-tenancy scoping
- [ ] `get_queryset` filters by `request.user.clinic`
- [ ] `perform_create` sets `clinic=request.user.clinic`
- [ ] Migration created and applied locally
- [ ] Serializer excludes `clinic` from writable fields (set in `perform_create`)
- [ ] API service function added
- [ ] Translation keys added to both `en.json` and `pl.json`
- [ ] Tests pass: `./venv/bin/pytest`
- [ ] Linting passes: `ruff check . && black --check .`
