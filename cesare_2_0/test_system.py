"""
Test del sistema CESARE 2.0
Verifica l'integrazione di tutti i nuovi moduli:
- Modelli Pydantic
- Assembly Engine (Clean-Pipe)
- Robust JSON Parser
- Orchestrator refactored
"""
import asyncio
import sys

async def test_models():
    """Test dei modelli Pydantic"""
    print("\n=== TEST 1: Modelli Pydantic ===")
    from core.models import AgentResult, ExecutionStatus, AgentRole, OrchestratorPlan, TaskDefinition
    from datetime import datetime
    
    # Test creazione AgentResult valido
    result = AgentResult(
        agent_id="test_1",
        role=AgentRole.RESEARCHER,
        status=ExecutionStatus.SUCCESS,
        content={"data": "test value"},
        execution_time_ms=123.45
    )
    print(f"✓ AgentResult creato: {result.agent_id}")
    
    # Test validazione fallita (content vuoto con status SUCCESS)
    try:
        bad_result = AgentResult(
            agent_id="test_2",
            role=AgentRole.CODER,
            status=ExecutionStatus.SUCCESS,
            content={},
            execution_time_ms=100.0
        )
        print("✗ Validazione fallita: avrebbe dovuto rifiutare content vuoto")
        return False
    except Exception as e:
        print(f"✓ Validazione corretta: rifiuta content vuoto ({type(e).__name__})")
    
    # Test OrchestratorPlan
    plan = OrchestratorPlan(
        plan_id="plan_001",
        objective="Test obiettivo",
        tasks=[
            TaskDefinition(task_id="t1", description="Task 1", priority=3)
        ],
        expected_outputs_schema={"t1": "output_desc"},
        synthesis_strategy="parallel_merge"
    )
    print(f"✓ OrchestratorPlan creato: {plan.plan_id}")
    
    return True


async def test_json_parser():
    """Test del RobustJSONParser"""
    print("\n=== TEST 2: Robust JSON Parser ===")
    from core.json_parser import RobustJSONParser
    
    parser = RobustJSONParser()
    
    # Test 1: JSON pulito
    clean_json = '{"key": "value", "number": 42}'
    data, error = parser.parse(clean_json)
    if error:
        print(f"✗ Parsing JSON pulito fallito: {error}")
        return False
    print(f"✓ JSON pulito parsato: {data}")
    
    # Test 2: JSON con blocco markdown
    markdown_json = '''Ecco il risultato:
```json
{
    "status": "success",
    "items": [1, 2, 3]
}
```
Fine del messaggio.'''
    data, error = parser.parse(markdown_json)
    if error:
        print(f"✗ Parsing JSON con markdown fallito: {error}")
        return False
    print(f"✓ JSON con markdown parsato: {data}")
    
    # Test 3: JSON con virgola finale extra (errore comune LLM)
    bad_json = '{"key": "value",}'
    data, error = parser.parse(bad_json)
    if error:
        print(f"⚠ Parsing JSON con virgola extra: {error}")
    else:
        print(f"✓ JSON corretto automaticamente: {data}")
    
    # Test 4: Input vuoto
    data, error = parser.parse("")
    if not error:
        print("✗ Dovrebbe fallire con input vuoto")
        return False
    print(f"✓ Input vuoto gestito correttamente: {error}")
    
    return True


async def test_assembly_engine():
    """Test dell'AssemblyEngine (Clean-Pipe)"""
    print("\n=== TEST 3: Assembly Engine (Clean-Pipe) ===")
    from core.models import AgentResult, ExecutionStatus, AgentRole, OrchestratorPlan, TaskDefinition
    from core.pipeline import AssemblyEngine
    
    engine = AssemblyEngine()
    
    # Crea risultati simulati
    results = [
        AgentResult(
            agent_id="research_1",
            role=AgentRole.RESEARCHER,
            status=ExecutionStatus.SUCCESS,
            content={"summary": "Dati trovati", "count": 42},
            execution_time_ms=150.0
        ),
        AgentResult(
            agent_id="code_1",
            role=AgentRole.CODER,
            status=ExecutionStatus.SUCCESS,
            content={"code": "print('hello')", "language": "python"},
            execution_time_ms=200.0
        ),
        AgentResult(
            agent_id="review_1",
            role=AgentRole.REVIEWER,
            status=ExecutionStatus.CRITICAL_FAIL,
            content={},
            error_message="Timeout durante la revisione",
            execution_time_ms=5000.0
        )
    ]
    
    plan = OrchestratorPlan(
        plan_id="test_plan",
        objective="Test completo",
        tasks=[
            TaskDefinition(task_id="research_1", description="Ricerca", priority=3, critical=True),
            TaskDefinition(task_id="code_1", description="Codice", priority=4, critical=True),
            TaskDefinition(task_id="review_1", description="Review", priority=2, critical=False)
        ],
        expected_outputs_schema={},
        synthesis_strategy="parallel_merge"
    )
    
    # Test validazione
    is_valid, errors = engine.validate_results(results, plan)
    print(f"✓ Validazione eseguita: is_valid={is_valid}, errori_critici={len(errors)}")
    
    # Test assembly contesto
    context = engine.assemble_context(results, plan)
    print(f"✓ Contesto assemblato: {len(context.summary_results)} risultati, {len(context.critical_failures)} fallimenti")
    
    # Test rendering prompt
    prompt = engine.render_prompt(context)
    if not prompt:
        print("✗ Prompt rendering fallito")
        return False
    print(f"✓ Prompt generato ({len(prompt)} caratteri)")
    print(f"\nAnteprima prompt:\n{prompt[:200]}...")
    
    return True


async def test_orchestrator():
    """Test dell'Orchestrator completo"""
    print("\n=== TEST 4: Orchestrator Completo ===")
    from core.orchestrator import Orchestrator
    
    orchestrator = Orchestrator()
    
    # Esegui un task completo
    result = await orchestrator.execute_task("Analizza dati e genera report")
    
    if result["status"] not in ["completed", "partial_success"]:
        print(f"✗ Esecuzione fallita: {result}")
        return False
    
    print(f"✓ Task eseguito: status={result['status']}")
    print(f"✓ Plan ID: {result['plan_id']}")
    print(f"✓ Fallimenti critici: {result['critical_failures']}")
    print(f"✓ Metadata: {result['metadata']}")
    print(f"\nRisposta finale (anteprima): {result['final_answer'][:100]}...")
    
    return True


async def main():
    print("=" * 60)
    print("CESARE 2.0 - Test Suite Completa")
    print("=" * 60)
    
    tests = [
        ("Modelli Pydantic", test_models),
        ("Robust JSON Parser", test_json_parser),
        ("Assembly Engine", test_assembly_engine),
        ("Orchestrator", test_orchestrator)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            success = await test_func()
            if success:
                passed += 1
                print(f"\n✅ {test_name}: SUPERATO")
            else:
                failed += 1
                print(f"\n❌ {test_name}: FALLITO")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name}: ECCEZIONE ({e})")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"RISULTATI: {passed} superati, {failed} falliti su {len(tests)} test")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
