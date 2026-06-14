from __future__ import annotations

import sounddevice as sd
import numpy as np

RATE = 16000
DURATION = 5

print("=" * 50)
print("  DarkSON - Teste de Microfone")
print("=" * 50)
print(f"\nFale algo nos próximos {DURATION} segundos...")
print()

audio = sd.rec(int(DURATION * RATE), samplerate=RATE, channels=1, dtype=np.int16, blocking=True)

nivel_max = np.max(np.abs(audio))
nivel_medio = np.mean(np.abs(audio))

print("-" * 50)
print(f"Nível máximo: {nivel_max}")
print(f"Nível médio:  {nivel_medio:.1f}")
print()

if nivel_max < 500:
    print(" Microfone parece estar MUITO BAIXO ou mudo.")
    print(" Verifique se o microfone está conectado e habilitado.")
elif nivel_max < 2000:
    print(" Microfone está funcionando mas BAIXO. Aproxime-se.")
elif nivel_max < 8000:
    print(" Microfone OK. Nível bom para reconhecimento.")
else:
    print(" Microfone PERFEITO. Nível excelente!")

print()
print("Taxa de amostragem: 16000 Hz")
print("Canais: 1 (mono)")
print("Formato: PCM int16")
print("=" * 50)
