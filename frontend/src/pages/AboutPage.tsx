import { Link } from "react-router-dom";

export default function AboutPage() {
  return (
    <div className="flex flex-col gap-6 max-w-lg mx-auto py-8">
      <div>
        <h1 className="text-2xl font-bold text-ink">Sobre BuscoMiPana</h1>
        <p className="text-muted text-sm mt-1">
          Una app de chequeo de estado y búsqueda de personas para emergencias en Colombia y Latinoamérica.
        </p>
      </div>

      <section className="flex flex-col gap-2 text-sm text-muted">
        <p>
          Cuando ocurre una emergencia — un sismo, una inundación, un apagón masivo, un
          desplazamiento — lo primero que la gente necesita saber es si sus seres queridos
          están bien. BuscoMiPana existe para responder esa pregunta lo más rápido posible,
          incluso con conexión débil o intermitente.
        </p>
        <p>
          Con solo su número de celular (sin contraseñas), cualquier persona puede reportar en
          segundos <span className="text-ink">&ldquo;Estoy bien&rdquo;</span> o{" "}
          <span className="text-ink">&ldquo;Necesito ayuda&rdquo;</span>, vincularse con sus
          familiares y contactos de confianza (&ldquo;panas&rdquo;) para que vean su estado, y
          reportar a alguien como desaparecido o localizado — incluso antes de que esa persona
          tenga una cuenta. El reporte se resuelve automáticamente en el momento en que esa
          persona se registra.
        </p>
        <p>
          La app está diseñada para funcionar bajo estrés y con recursos limitados: interfaz
          simple de alto contraste, bajo consumo de datos y batería, y modo sin conexión que
          guarda su estado localmente hasta que vuelva la señal.
        </p>
      </section>

      <section className="flex flex-col gap-2 text-sm text-muted border-t border-card pt-4">
        <h2 className="text-ink font-semibold">Cómo usamos los números de teléfono</h2>
        <p>
          El número de teléfono es la identidad de la cuenta: se usa para enviar un código de
          verificación de un solo uso (OTP) al iniciar sesión, y para notificar a familiares
          vinculados sobre cambios de estado. No enviamos mensajes de mercadeo ni contenido no
          solicitado — todo el tráfico de SMS es transaccional y iniciado por una acción directa
          de la persona usuaria (crear cuenta, iniciar sesión, o un pariente vinculado
          respondiendo a un cambio de estado).
        </p>
      </section>

      <section className="flex flex-col gap-2 text-sm text-muted border-t border-card pt-4">
        <h2 className="text-ink font-semibold">About BuscoMiPana (English summary)</h2>
        <p>
          BuscoMiPana is a phone-first, offline-friendly safety check-in and missing-person
          matching platform for Colombia and Latin America. Users create an account with just a
          phone number (OTP, no password), report their own status ("I'm OK" / "I need help"),
          link with relatives to share status updates, and report someone as missing — a report
          that auto-resolves the moment that phone number signs up. All SMS traffic is
          transactional (OTP codes and status-change notifications triggered directly by a
          user's own action), never marketing or unsolicited content.
        </p>
      </section>

      <footer className="text-xs text-muted border-t border-card pt-4 flex flex-col gap-1">
        <p>Contacto: contact@buscomipana.com</p>
        <div className="flex gap-3">
          <Link to="/login" className="underline decoration-dotted hover:text-ink">
            Volver al inicio
          </Link>
        </div>
      </footer>
    </div>
  );
}
