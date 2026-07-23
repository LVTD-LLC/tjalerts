from django.urls import path

from .views import (
    CompaniesJobsView,
    CompanyJobsView,
    HighestPaidJobsView,
    PostDetailView,
    PostListView,
    TechnologiesJobsView,
    TechnologyJobsView,
    TitleJobsView,
    TitlesJobsView,
    create_backfill_vector_data_jobs_view,
    find_bad_submitted_dates_view,
    import_remote_ok_jobs_view,
    import_we_work_remotely_jobs_view,
    update_min_and_max_salary_view,
)

urlpatterns = [
    path("", PostListView.as_view(), name="posts"),
    path("<uuid:pk>", PostDetailView.as_view(), name="post"),
    path("find_bad_submitted_dates/", find_bad_submitted_dates_view, name="find-bad-submitted-dates"),
    path("update_min_and_max_salary/", update_min_and_max_salary_view, name="update_min_and_max_salary"),
    path("import_remote_ok_jobs/", import_remote_ok_jobs_view, name="import_remote_ok_jobs"),
    path("import_we_work_remotely_jobs/", import_we_work_remotely_jobs_view, name="import_we_work_remotely_jobs"),
    path(
        "create_backfill_vector_data_jobs/<int:rebuild>/",
        create_backfill_vector_data_jobs_view,
        name="create_backfill_vector_data_jobs",
    ),
    # path("highest-paid-list", HighestPaidBlogPostListView.as_view(), name="highest-paid-blog-posts"),
    path("companies/", CompaniesJobsView.as_view(), name="companies"),
    path("company/<slug:slug>/", CompanyJobsView.as_view(), name="company-jobs"),
    path("technologies/", TechnologiesJobsView.as_view(), name="technologies"),
    path("technology/<slug:slug>/", TechnologyJobsView.as_view(), name="technology-jobs"),
    path("titles/", TitlesJobsView.as_view(), name="titles"),
    path("title/<slug:slug>/", TitleJobsView.as_view(), name="title-jobs"),
    path("<slug:slug>/highest-paid/", HighestPaidJobsView.as_view(), name="highest-paid-job-blog-post"),
]
