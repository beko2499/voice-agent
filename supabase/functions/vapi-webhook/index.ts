import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

/**
 * Safely parse tool call arguments.
 * VAPI may send arguments as a JSON string OR as an already-parsed object.
 */
function parseArgs(raw: unknown): Record<string, string> {
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw);
    } catch {
      console.error("Failed to parse arguments string:", raw);
      return {};
    }
  }
  if (typeof raw === 'object' && raw !== null) {
    return raw as Record<string, string>;
  }
  return {};
}

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? '';
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
    const supabase = createClient(supabaseUrl, supabaseKey);

    const body = await req.json();
    console.log("=== VAPI WEBHOOK RECEIVED ===");
    console.log("Full body:", JSON.stringify(body, null, 2));

    const message = body.message;

    // --- Handle different VAPI payload formats ---
    // VAPI can send the payload in different structures depending on the version.
    // Format 1: { message: { type: "tool-calls", toolCallList: [...] } }
    // Format 2: { message: { type: "tool-calls", toolWithToolCallList: [...] } }
    // Format 3 (newer): { message: { toolCalls: [...] } } with type "tool-calls"

    if (!message) {
      console.error("No 'message' field in body. Full body keys:", Object.keys(body));
      return new Response(JSON.stringify({ error: "No message field in request body" }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 400,
      });
    }

    if (message.type !== 'tool-calls') {
      console.log("Non tool-calls message type:", message.type);
      return new Response(JSON.stringify({ error: `Unexpected message type: '${message.type}'` }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 400,
      });
    }

    const results: Array<{ toolCallId: string; result: string }> = [];

    // Support both VAPI payload structures
    const toolCalls = message.toolCallList || message.toolWithToolCallList || [];
    console.log(`Processing ${toolCalls.length} tool call(s)`);

    for (const item of toolCalls) {
      // Handle both structures:
      // toolWithToolCallList: { toolCall: { id, function: { name, arguments } } }
      // toolCallList: { id, function: { name, arguments } }
      const toolCall = item.toolCall || item;
      const toolCallId = toolCall.id;
      const functionName = toolCall.function?.name;
      const rawArgs = toolCall.function?.arguments;

      // Parse arguments safely — VAPI sometimes sends them as a JSON string
      const args = parseArgs(rawArgs);

      console.log(`--- Tool: ${functionName} ---`);
      console.log(`  toolCallId: ${toolCallId}`);
      console.log(`  rawArgs type: ${typeof rawArgs}`);
      console.log(`  rawArgs value: ${JSON.stringify(rawArgs)}`);
      console.log(`  parsed args: ${JSON.stringify(args)}`);

      if (functionName === 'check_availability') {
        const date = args.date;

        if (!date) {
          console.error("check_availability called but 'date' is missing from args!");
          results.push({
            toolCallId,
            result: "I need a date to check availability. Please provide a date."
          });
          continue;
        }

        console.log(`  Querying appointments for date: ${date}`);

        // Get booked appointments for the date
        const { data, error } = await supabase
          .from('appointments')
          .select('appointment_time')
          .eq('appointment_date', date);

        if (error) {
          console.error("DB Error:", JSON.stringify(error));
          results.push({
            toolCallId,
            result: `Error checking availability: ${error.message}`
          });
          continue;
        }

        console.log(`  Booked appointments found: ${data?.length ?? 0}`, JSON.stringify(data));

        const bookedTimes = (data || []).map((app: { appointment_time: string }) => 
          app.appointment_time.substring(0, 5)
        );
        
        // Define all possible slots (9 AM to 5 PM)
        const allSlots = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"];
        const availableSlots = allSlots.filter(slot => !bookedTimes.includes(slot));

        console.log(`  Booked times: [${bookedTimes.join(', ')}]`);
        console.log(`  Available slots: [${availableSlots.join(', ')}]`);

        if (availableSlots.length === 0) {
          results.push({
            toolCallId,
            result: `Sorry, there are no available appointments on ${date}. All slots are fully booked. Please try another date.`
          });
        } else {
          results.push({
            toolCallId,
            result: `The available appointment times on ${date} are: ${availableSlots.join(', ')}. Please ask the customer to choose one of these times.`
          });
        }

      } else if (functionName === 'book_appointment') {
        const customer_name = args.customer_name;
        const phone_number = args.phone_number;
        const date = args.date;
        const time = args.time;

        if (!customer_name || !date || !time) {
          console.error("book_appointment missing required args:", { customer_name, phone_number, date, time });
          results.push({
            toolCallId,
            result: "Missing required information. I need the customer name, date, and time to book an appointment."
          });
          continue;
        }

        console.log(`  Booking: ${customer_name} on ${date} at ${time}`);

        // Ensure time format includes seconds for the DB
        const dbTime = time.length === 5 ? time + ':00' : time;

        // Try to insert the appointment
        const { data, error } = await supabase
          .from('appointments')
          .insert([
            {
              customer_name,
              phone_number: phone_number || 'N/A',
              appointment_date: date,
              appointment_time: dbTime,
              status: 'CONFIRMED'
            }
          ]);

        if (error) {
          console.error("Booking Error:", JSON.stringify(error));
          if (error.code === '23505') { // Unique constraint violation
            results.push({
              toolCallId,
              result: `Sorry, the time slot ${time} on ${date} is already booked by another patient. Please choose a different time.`
            });
          } else {
            results.push({
              toolCallId,
              result: `Error booking appointment: ${error.message}`
            });
          }
        } else {
          console.log("  Booking SUCCESS");
          results.push({
            toolCallId,
            result: `Appointment successfully booked! ${customer_name} is confirmed for ${date} at ${time}. Please let the customer know their appointment is confirmed.`
          });
        }

      } else {
        console.warn(`  Unknown function: ${functionName}`);
        results.push({
          toolCallId,
          result: `Unknown tool function: ${functionName}`
        });
      }
    }

    const responsePayload = { results };
    console.log("=== SENDING RESPONSE TO VAPI ===");
    console.log(JSON.stringify(responsePayload, null, 2));

    return new Response(JSON.stringify(responsePayload), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 200,
    });

  } catch (error) {
    console.error("=== UNHANDLED ERROR ===", error);
    return new Response(JSON.stringify({ error: error.message }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 500,
    });
  }
});
