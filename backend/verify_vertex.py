
from app.config import get_settings
from app.services.intent_service import IntentService


def main():
    settings = get_settings()

    print("Project:", settings.google_cloud_project)
    print("Location:", settings.google_cloud_location)
    print("Model:", settings.gemini_model)
    print("Mode:", settings.ai_mode)

    service = IntentService(settings)

    response = service.extract(
        "I need a 65W USB-C PD charger under "
        "₹1000 before 6 PM. It must work with my laptop."
    )

    print("\n=== GEMINI EXTRACTION RESULT ===")
    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
