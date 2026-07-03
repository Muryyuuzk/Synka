from pathlib import Path

from synka_lens.config import load_database_config
from synka_lens.domain.machine_state import StatusThresholds
from synka_lens.transformation.bronze import write_bronze
from synka_lens.transformation.silver import write_silver
from synka_lens.transformation.gold import compute_availability

# Configuracao da aplicacao: limiares de dominio calibrados sobre dados reais.
# Ficam aqui, explicitos, como ponto unico de definicao para a execucao real.
THRESHOLDS = StatusThresholds(
    running_above_value=40.0,
    gap_seconds=30.0,
)

DATA_DIR = Path("data")
BRONZE_PATH = DATA_DIR / "bronze" / "sensor_readings"
SILVER_PATH = DATA_DIR / "silver" / "sensor_readings"


def _ensure_output_directories() -> None:
    BRONZE_PATH.mkdir(parents=True, exist_ok=True)
    SILVER_PATH.mkdir(parents=True, exist_ok=True)


def run_pipeline() -> None:
    config = load_database_config()
    _ensure_output_directories()

    print("Executando camada bronze...")
    bronze_count = write_bronze(config, BRONZE_PATH)
    print(f"  bronze: {bronze_count} leituras materializadas")

    if bronze_count == 0:
        print("Nenhuma leitura na fonte. Pipeline encerrado.")
        return

    print("Executando camada silver...")
    silver_count = write_silver(BRONZE_PATH, SILVER_PATH, THRESHOLDS)
    print(f"  silver: {silver_count} leituras processadas")

    print("Executando camada gold...")
    metrics = compute_availability(SILVER_PATH, THRESHOLDS)
    print(f"  gold: {len(metrics)} maquina(s) com metricas calculadas")

    for m in metrics:
        print(
            f"    {m.tag}: disponibilidade {m.availability_percent:.1f}% "
            f"(rodando {m.running_seconds:.0f}s, parada {m.stopped_seconds:.0f}s, "
            f"gap {m.gap_seconds:.0f}s)"
        )


if __name__ == "__main__":
    run_pipeline()
