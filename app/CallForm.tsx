const CallForm = ({
  sendInformation,
}: {
  sendInformation: (formData: FormData) => void;
}) => {
  return (
    <form
      action={sendInformation}
      className="flex flex-col bg-black p-4 gap-4 rounded-md w-4/5"
    >
      <div className="flex flex-col">
        <label htmlFor="phone-number" className="text-white">
          Phone number
        </label>

        <input
          type="text"
          id="phone-number"
          name="phoneNumber"
          required
          className="bg-white text-black rounded-xs h-7"
        />
      </div>

      <div className="flex flex-col">
        <label htmlFor="link" className="text-white">
          Link to job posting
        </label>

        <input
          type="text"
          id="link"
          name="link"
          required
          className="bg-white text-black rounded-xs h-7"
        />
      </div>

      <div className="flex flex-col">
        <label htmlFor="questions" className="text-white">
          Questions
        </label>

        <textarea
          id="questions"
          name="questions"
          rows={4}
          required
          className="bg-white text-black rounded-xs"
        ></textarea>
      </div>

      <button
        type="submit"
        className="w-fit self-end px-5 py-2 bg-white text-black rounded-sm"
      >
        Submit
      </button>
    </form>
  );
};

export default CallForm;
