"""Production application source allowlist shared by build paths."""
MODULES = ['quick_app','app_paths','resource_policy','hardware_check','model_setup',
           'analysis_cache','production_pipeline','presentation_results','analysis_worker','pipeline_timing',
           'plot_support','piano','main_notes','game_notes','curve_reliability',
           'pitch_modes','pitch_experiments','analyze_song','lab','rmvpe_adapter',
           'benchmark_vocadito','prepare_game_notes','vocal_separator','separation_execution','separation_pool','hysteresis_experiment']
RESOURCES = ['qml','assets','resources','note-settings.json','LICENSE',
             'THIRD_PARTY_NOTICES.md']
VENDOR = ['__init__.py','rmvpe_rvc.py','LICENSE-RVC','MODEL-CARD-RVC.md','provenance.json']
